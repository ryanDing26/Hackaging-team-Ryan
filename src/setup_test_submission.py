#!/usr/bin/env python3
"""
Setup and Test - Submission Format Agent
Works with your existing codebase structure
"""

import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'src'))
from dotenv import load_dotenv
load_dotenv()


def check_requirements():
    """Check required packages"""
    print("🔍 Checking requirements...")
    
    required = {
        'anthropic': 'pip install anthropic',
        'requests': 'pip install requests',
    }
    
    missing = []
    for package, install_cmd in required.items():
        pkg_name = package.replace('-', '_')  # python-dotenv -> python_dotenv
        try:
            __import__(pkg_name)
            print(f"  ✓ {package}")
        except ImportError:
            print(f"  ❌ {package} - Run: {install_cmd}")
            missing.append(package)
    
    return len(missing) == 0


def check_env_vars():
    """Check environment variables"""
    print("\n🔍 Checking environment variables...")
    
    required = {
        'ANTHROPIC_API_KEY': 'Your Claude API key',
        'PUBMED_EMAIL': 'Your email for PubMed API'
    }
    
    missing = []
    for var, description in required.items():
        value = os.getenv(var)
        if value:
            masked = value[:8] + "..." if len(value) > 8 else "***"
            print(f"  ✓ {var} = {masked}")
        else:
            print(f"  ❌ {var} - {description}")
            missing.append(var)
    
    if missing:
        print("\n💡 To set environment variables:")
        print("   1. Create a .env file in project root")
        print("   2. Add these lines:")
        print("      ANTHROPIC_API_KEY=your-key-here")
        print("      PUBMED_EMAIL=your-email@example.com")
    
    return len(missing) == 0


def test_anthropic_connection():
    """Test Anthropic API"""
    print("\n🔍 Testing Anthropic API connection...")
    
    try:
        from anthropic import Anthropic
        
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            print("  ❌ No API key found")
            return False
        
        client = Anthropic(api_key=api_key)
        
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=50,
            messages=[{"role": "user", "content": "Say 'API working' and nothing else."}]
        )
        
        result = response.content[0].text
        print(f"  ✓ API Response: {result}")
        return True
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def test_pubmed_connection():
    """Test PubMed API"""
    print("\n🔍 Testing PubMed API connection...")
    
    try:
        import requests
        
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {
            'db': 'pubmed',
            'term': 'aging',
            'retmax': 1,
            'retmode': 'json'
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        count = data.get('esearchresult', {}).get('count', 0)
        print(f"  ✓ PubMed accessible ({count} papers on 'aging')")
        return True
        
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def run_test_paper():
    """Run agent on 1 test paper"""
    print("\n🚀 Running test with 1 paper...")
    print("   (This will cost ~$0.04 and take ~30 seconds)")
    
    response = input("\nProceed with test? [y/N]: ")
    if response.lower() != 'y':
        print("Test skipped.")
        return True
    
    try:
        # Import the correct submission agent
        # First, try to import from the file we just created
        agent_file = Path(__file__).parent / "aging_agent.py"
        
        if agent_file.exists():
            print(f"\n✓ Using: {agent_file}")
            import importlib.util
            spec = importlib.util.spec_from_file_location("submission_agent", agent_file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            SubmissionAgent = module.SubmissionAgent
        else:
            # Try importing from src directory
            from aging_agent_pubmed import SubmissionAgent
        
        # Create test output directory
        test_dir = Path("test_submission")
        test_dir.mkdir(exist_ok=True)
        
        # Initialize agent
        print("\nInitializing agent...")
        agent = SubmissionAgent(output_dir=str(test_dir))
        
        # Run with 1 paper
        print("\n" + "="*80)
        agent.run(
            initial_query="aging mechanisms[Title/Abstract] AND mitochondria",
            target_papers=1,
            max_cost_usd=0.50
        )
        print("="*80)
        
        # Check outputs
        print("\n📁 Checking output files...")
        expected_files = [
            test_dir / "table1_theories.csv",
            test_dir / "table2_papers.csv",
            test_dir / "table3_annotations.csv"
        ]
        
        all_exist = True
        for file in expected_files:
            if file.exists():
                size = file.stat().st_size
                print(f"  ✓ {file.name} ({size} bytes)")
                
                # Show sample
                with open(file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    if len(lines) > 1:
                        print(f"    Header: {lines[0].strip()}")
                        print(f"    Data: {lines[1].strip()[:100]}...")
            else:
                print(f"  ❌ {file.name} not created")
                all_exist = False
        
        # Check supplementary
        supp_dir = test_dir / "supplementary"
        if supp_dir.exists():
            print(f"\n  ✓ Supplementary directory created")
            supp_files = list(supp_dir.glob("*.csv"))
            print(f"    {len(supp_files)} quality control files")
        
        if all_exist:
            print("\n✅ Test successful! All files created.")
            print(f"\n📂 Check output: {test_dir}/")
            
            # Verify format
            print("\n🔍 Verifying format...")
            try:
                import csv
                
                # Check table1 format
                with open(expected_files[0], 'r') as f:
                    reader = csv.DictReader(f)
                    required = ['theory_id', 'theory_name', 'number_of_collected_papers']
                    if list(reader.fieldnames) == required:
                        print("  ✓ Table 1 format correct")
                    else:
                        print(f"  ⚠ Table 1 format issue: {reader.fieldnames}")
                
                # Check table2 format
                with open(expected_files[1], 'r') as f:
                    reader = csv.DictReader(f)
                    required = ['theory_id', 'paper_url', 'paper_name', 'paper_year']
                    if list(reader.fieldnames) == required:
                        print("  ✓ Table 2 format correct")
                    else:
                        print(f"  ⚠ Table 2 format issue: {reader.fieldnames}")
                
                # Check table3 format
                with open(expected_files[2], 'r') as f:
                    reader = csv.DictReader(f)
                    required = ['theory_id', 'paper_url', 'paper_name', 'paper_year',
                               'Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Q6', 'Q7', 'Q8', 'Q9']
                    if list(reader.fieldnames) == required:
                        print("  ✓ Table 3 format correct")
                    else:
                        print(f"  ⚠ Table 3 format issue: {reader.fieldnames}")
                
                print("\n✅ Format verification passed!")
                
            except Exception as e:
                print(f"\n⚠️  Verification error: {e}")
        else:
            print("\n⚠️  Some files missing.")
        
        return all_exist
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main setup flow"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║   SETUP & TEST - Submission Format Agent                    ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    # Run checks
    checks = {
        "Requirements": check_requirements(),
        "Environment": check_env_vars(),
        "Anthropic API": test_anthropic_connection(),
        "PubMed API": test_pubmed_connection(),
    }
    
    # Summary
    print("\n" + "="*80)
    print("SETUP SUMMARY")
    print("="*80)
    
    all_passed = True
    for check_name, passed in checks.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{check_name:20} {status}")
        if not passed:
            all_passed = False
    
    if not all_passed:
        print("\n⚠️  Please fix the failed checks above before proceeding.")
        print("\nCommon fixes:")
        print("  - Install packages: pip install -r requirements.txt")
        print("  - Create .env file with your API keys")
        print("  - export ANTHROPIC_API_KEY='your-key-here'")
        return 1
    
    # Run test
    test_passed = run_test_paper()
    print(test_passed)

if __name__ == "__main__":
    sys.exit(main())