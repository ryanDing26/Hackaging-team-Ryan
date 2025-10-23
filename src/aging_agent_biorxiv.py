"""
Submission-Format Aging Research Agent - BioRxiv Version
Produces EXACTLY the 3 required CSV files for submission
"""

import os
import json
import time
import csv
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import requests
from anthropic import Anthropic
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

# Configuration - BioRxiv API
BIORXIV_BASE_URL = "http://api.biorxiv.org"


@dataclass
class TheoryTag:
    """Theory tag with confidence score"""
    theory_id: int
    theory_name: str
    confidence: float
    evidence_snippets: List[str]
    source: str


class FullTextRetriever:
    """Placeholder - BioRxiv doesn't provide full text via API"""
    
    def __init__(self, email: str):
        self.email = email
    
    def get_full_text(self, doi: str) -> Tuple[Optional[str], Optional[str]]:
        """BioRxiv doesn't provide full text via API"""
        return None, None


class SubmissionAgent:
    """Agent producing submission-format CSVs"""
    
    def __init__(
        self,
        anthropic_api_key: Optional[str] = None,
        pubmed_email: Optional[str] = None,
        output_dir: str = "submission_output"
    ):
        self.api_key = anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.email = pubmed_email or os.environ.get("PUBMED_EMAIL", "research@example.com")
        
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY must be set")
        
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.supplementary_dir = self.output_dir / "supplementary"
        self.supplementary_dir.mkdir(exist_ok=True)
        
        # Initialize components
        self.client = Anthropic(api_key=self.api_key)
        self.model = "claude-sonnet-4-20250514"
        self.full_text_retriever = FullTextRetriever(email=self.email)
        
        # Aging theories
        self.theories = {
            1: "Free Radical Theory",
            2: "Telomere Shortening",
            3: "Mitochondrial Dysfunction",
            4: "Cellular Senescence",
            5: "Stem Cell Exhaustion",
            6: "Altered Intercellular Communication",
            7: "Loss of Proteostasis",
            8: "Deregulated Nutrient Sensing",
            9: "Genomic Instability",
            10: "Epigenetic Alterations"
        }
        
        # Track theory-paper mappings
        self.theory_papers = {}  # theory_id -> list of papers
        
        # Statistics
        self.stats = {
            'papers_processed': 0,
            'full_text_retrieved': 0,
            'high_confidence': 0,
            'total_cost': 0.0,
            'start_time': time.time()
        }
        
        # CSV files - SUBMISSION FORMAT
        self.table1_file = self.output_dir / "table1_theories.csv"
        self.table2_file = self.output_dir / "table2_papers.csv"
        self.table3_file = self.output_dir / "table3_annotations.csv"
        
        # Supplementary files
        self.quality_file = self.supplementary_dir / "quality_metrics.csv"
        self.theory_tags_file = self.supplementary_dir / "theory_tags_detailed.csv"
        self.metadata_file = self.supplementary_dir / "paper_metadata.csv"
        
        self._initialize_csv_files()
    
    def _initialize_csv_files(self):
        """Initialize all CSV files"""
        
        # SUBMISSION TABLES
        if not self.table1_file.exists():
            with open(self.table1_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['theory_id', 'theory_name', 'number_of_collected_papers'])
        
        if not self.table2_file.exists():
            with open(self.table2_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['theory_id', 'paper_url', 'paper_name', 'paper_year'])
        
        if not self.table3_file.exists():
            with open(self.table3_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'theory_id', 'paper_url', 'paper_name', 'paper_year',
                    'Q1', 'Q2', 'Q3', 'Q4', 'Q5', 'Q6', 'Q7', 'Q8', 'Q9'
                ])
        
        # SUPPLEMENTARY TABLES
        if not self.quality_file.exists():
            with open(self.quality_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'paper_url', 'question', 'is_valid', 'confidence',
                    'issues', 'evidence', 'corrected_answer'
                ])
        
        if not self.theory_tags_file.exists():
            with open(self.theory_tags_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'paper_url', 'theory_id', 'theory_name', 'confidence',
                    'evidence_snippets', 'source'
                ])
        
        if not self.metadata_file.exists():
            with open(self.metadata_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'paper_url', 'pmid', 'title', 'abstract', 'authors', 'journal',
                    'has_full_text', 'full_text_source', 'overall_confidence',
                    'processing_time'
                ])
    
    def search_pubmed(self, query: str, max_results: int = 100) -> List[str]:
        """Search BioRxiv - returns DOIs"""
        try:
            # Clean query - remove PubMed syntax
            clean_query = query.replace('[Title/Abstract]', '').replace('[Title]', '').replace('[Abstract]', '').strip()
            
            # BioRxiv doesn't have a search API, so get recent papers and filter
            from datetime import datetime, timedelta
            end_date = datetime.now()
            start_date = end_date - timedelta(days=730)  # Last 2 years
            
            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")
            
            # BioRxiv API: get papers in date range
            # Need to paginate through cursor values
            dois = []
            cursor = 0
            
            while len(dois) < max_results and cursor < 10:  # Limit to 10 API calls
                url = f"{BIORXIV_BASE_URL}/details/biorxiv/{start_str}/{end_str}/{cursor}/json"
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                collection = data.get('collection', [])
                
                if not collection:
                    break
                
                # Filter by query terms
                query_lower = clean_query.lower()
                query_terms = [term.strip() for term in query_lower.split() 
                              if len(term.strip()) > 2]  # Only words longer than 2 chars
                
                for paper in collection:
                    title = paper.get('title', '').lower()
                    abstract = paper.get('abstract', '').lower()
                    combined = title + ' ' + abstract
                    
                    # Check if ANY query term appears
                    if query_terms and any(term in combined for term in query_terms):
                        doi = paper.get('doi')
                        if doi:
                            dois.append(doi)
                            if len(dois) >= max_results:
                                break
                
                cursor += 1
                time.sleep(0.3)  # Rate limiting
            
            return dois[:max_results]
            
        except Exception as e:
            print(f"Error searching BioRxiv: {e}")
            return []
    
    def fetch_metadata(self, pmid: str) -> Optional[Dict]:
        """Fetch paper metadata from BioRxiv - pmid is actually a DOI"""
        try:
            url = f"{BIORXIV_BASE_URL}/details/biorxiv/{pmid}"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            collection = data.get('collection', [])
            
            if not collection:
                return None
            
            paper = collection[0]
            
            # Extract authors
            authors_str = paper.get('authors', '')
            authors = [a.strip() for a in authors_str.split(';') if a.strip()]
            
            # Extract year
            date_str = paper.get('date', '')
            year = 0
            if date_str:
                try:
                    year = int(date_str.split('-')[0])
                except:
                    pass
            
            return {
                'pmid': pmid,
                'title': paper.get('title', ''),
                'abstract': paper.get('abstract', ''),
                'year': year,
                'authors': authors,
                'journal': 'bioRxiv',
                'url': f"https://www.biorxiv.org/content/{pmid}"
            }
            
        except Exception as e:
            print(f"Error fetching metadata: {e}")
            return None
    
    def tag_theories(self, pmid: str, title: str, text: str) -> List[TheoryTag]:
        """Identify aging theories in paper"""
        text_sample = text[:100000] if len(text) > 100000 else text
        
        prompt = f"""Analyze this aging research paper and identify ALL relevant aging theories.

**Title:** {title}
**Text:** {text_sample}

**Known Theories:**
{json.dumps(self.theories, indent=2)}

For EACH relevant theory, provide:
- theory_id (from list, or 0 for novel)
- theory_name
- confidence (0.0-1.0)
- evidence_snippets (2-3 quotes)

Output JSON:
{{
    "theory_tags": [
        {{
            "theory_id": 1,
            "theory_name": "Free Radical Theory",
            "confidence": 0.9,
            "evidence_snippets": ["quote1", "quote2"]
        }}
    ]
}}

Be thorough - include all relevant theories."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            text_resp = response.content[0].text.strip()
            
            # Extract JSON
            if '```' in text_resp:
                parts = text_resp.split('```')
                for part in parts:
                    part = part.strip()
                    if part.startswith('json'):
                        part = part[4:].strip()
                    if part.startswith('{'):
                        text_resp = part
                        break
            
            if not text_resp.startswith('{'):
                start = text_resp.find('{')
                end = text_resp.rfind('}')
                if start != -1 and end != -1:
                    text_resp = text_resp[start:end+1]
            
            result = json.loads(text_resp.strip())
            
            tags = []
            for tag_data in result.get("theory_tags", []):
                tags.append(TheoryTag(
                    theory_id=tag_data["theory_id"],
                    theory_name=tag_data["theory_name"],
                    confidence=tag_data["confidence"],
                    evidence_snippets=tag_data.get("evidence_snippets", []),
                    source="full_text" if len(text) > 1000 else "abstract"
                ))
            
            # Fallback if no tags
            if not tags:
                print(f"  ⚠ No theories found, using keyword inference...")
                tags = self._infer_theories(text)
            
            return tags
            
        except Exception as e:
            print(f"  ⚠ Error tagging: {e}, using fallback...")
            return self._infer_theories(text)
    
    def _infer_theories(self, text: str) -> List[TheoryTag]:
        """Keyword-based fallback"""
        text_lower = text.lower()
        tags = []
        
        keywords = {
            1: (["free radical", "ros", "reactive oxygen", "oxidative stress"], "Free Radical Theory"),
            2: (["telomere", "telomerase"], "Telomere Shortening"),
            3: (["mitochondria", "mitochondrial"], "Mitochondrial Dysfunction"),
            4: (["senescence", "senescent"], "Cellular Senescence"),
            8: (["mtor", "nutrient sensing", "insulin"], "Deregulated Nutrient Sensing"),
            9: (["dna damage", "genomic instability"], "Genomic Instability"),
        }
        
        for theory_id, (kws, name) in keywords.items():
            for kw in kws:
                if kw in text_lower:
                    tags.append(TheoryTag(
                        theory_id=theory_id,
                        theory_name=name,
                        confidence=0.6,
                        evidence_snippets=[f"Keyword '{kw}' found"],
                        source="keyword_inference"
                    ))
                    break
        
        if not tags:
            tags = [TheoryTag(
                theory_id=0,
                theory_name="General Aging Research",
                confidence=0.5,
                evidence_snippets=["No specific keywords found"],
                source="default"
            )]
        
        return tags
    
    def extract_answers(self, pmid: str, title: str, text: str) -> Dict[str, str]:
        """Extract answers to 9 questions"""
        
        prompt = f"""Answer these 9 questions about this aging paper.

**Title:** {title}
**Text:** {text[:50000]}

Q1: Does it suggest an aging biomarker?
Answer: "Yes, quantitatively shown" / "Yes, but not shown" / "No"

Q2-Q9: Does it suggest a molecular mechanism? longevity intervention? claim aging cannot be reversed? biomarker for species differences? explain naked mole rat? explain birds? explain large animals? explain calorie restriction?
Answer: "Yes" / "No"

Output JSON only:
{{"Q1": "...", "Q2": "...", ..., "Q9": "..."}}"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )
            
            text_resp = response.content[0].text.strip()
            if '```' in text_resp:
                text_resp = text_resp.split('```')[1]
                if text_resp.startswith('json'):
                    text_resp = text_resp[4:]
            
            answers = json.loads(text_resp.strip())
            
            # Validate
            valid_q1 = ["Yes, quantitatively shown", "Yes, but not shown", "No"]
            valid_yes_no = ["Yes", "No"]
            
            if answers.get("Q1") not in valid_q1:
                answers["Q1"] = "No"
            
            for i in range(2, 10):
                if answers.get(f"Q{i}") not in valid_yes_no:
                    answers[f"Q{i}"] = "No"
            
            return answers
            
        except Exception as e:
            print(f"  Error extracting: {e}")
            return {"Q1": "No", **{f"Q{i}": "No" for i in range(2, 10)}}
    
    def process_paper(self, pmid: str) -> bool:
        """Process single paper"""
        start_time = time.time()
        
        print(f"\n{'='*80}")
        print(f"Processing DOI: {pmid}")
        
        # Fetch metadata
        print("Step 1: Fetching metadata...")
        metadata = self.fetch_metadata(pmid)
        if not metadata:
            print("  ❌ Failed")
            return False
        print(f"  ✓ {metadata['title'][:60]}...")
        
        # Attempt full text
        print("\nStep 2: Attempting full text...")
        full_text, source = self.full_text_retriever.get_full_text(pmid)
        has_full_text = full_text is not None
        
        if has_full_text:
            print(f"  ✓ Retrieved from {source}")
            self.stats['full_text_retrieved'] += 1
            text = full_text
        else:
            print("  ⚠ Using abstract only")
            text = metadata['abstract']
        
        # Tag theories
        print("\nStep 3: Tagging theories...")
        theory_tags = self.tag_theories(pmid, metadata['title'], text)
        print(f"  ✓ Found {len(theory_tags)} theories:")
        for tag in theory_tags:
            print(f"    - {tag.theory_name} ({tag.confidence:.2f})")
        
        # Extract answers
        print("\nStep 4: Extracting answers...")
        answers = self.extract_answers(pmid, metadata['title'], text)
        print(f"  ✓ Q1-Q9 extracted")
        
        # Calculate confidence
        confidence = "high" if has_full_text else "medium"
        
        processing_time = time.time() - start_time
        print(f"\nOverall confidence: {confidence.upper()}")
        print(f"⏱ Processing time: {processing_time:.2f}s")
        
        # Save to CSVs
        self._save_paper_to_csvs(metadata, theory_tags, answers, has_full_text, source, confidence, processing_time)
        
        self.stats['papers_processed'] += 1
        self.stats['total_cost'] += 0.04
        
        print(f"💰 Estimated total cost: ${self.stats['total_cost']:.2f}")
        
        return True
    
    def _save_paper_to_csvs(self, metadata, theory_tags, answers, has_full_text, source, confidence, processing_time):
        """Save paper to all CSV files"""
        
        paper_url = metadata['url']
        paper_name = metadata['title']
        paper_year = metadata['year']
        
        # Use primary (highest confidence) theory
        primary_theory = max(theory_tags, key=lambda t: t.confidence)
        theory_id = primary_theory.theory_id
        
        # Track for table1
        if theory_id not in self.theory_papers:
            self.theory_papers[theory_id] = []
        self.theory_papers[theory_id].append(paper_url)
        
        # TABLE 2: Papers
        with open(self.table2_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([theory_id, paper_url, paper_name, paper_year])
        
        # TABLE 3: Annotations
        with open(self.table3_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                theory_id, paper_url, paper_name, paper_year,
                answers['Q1'], answers['Q2'], answers['Q3'], answers['Q4'], answers['Q5'],
                answers['Q6'], answers['Q7'], answers['Q8'], answers['Q9']
            ])
        
        # SUPPLEMENTARY: Theory tags
        with open(self.theory_tags_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for tag in theory_tags:
                writer.writerow([
                    paper_url, tag.theory_id, tag.theory_name, f"{tag.confidence:.3f}",
                    " | ".join(tag.evidence_snippets[:2]), tag.source
                ])
        
        # SUPPLEMENTARY: Metadata
        with open(self.metadata_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                paper_url, metadata['pmid'], metadata['title'], metadata['abstract'],
                "; ".join(metadata['authors'][:5]), metadata['journal'],
                has_full_text, source or "N/A", confidence, f"{processing_time:.2f}"
            ])
    
    def finalize_table1(self):
        """Write table1 with theory counts"""
        print("\n📊 Finalizing table1_theories.csv...")
        
        with open(self.table1_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for theory_id, papers in self.theory_papers.items():
                theory_name = self.theories.get(theory_id, f"Unknown Theory {theory_id}")
                count = len(papers)
                writer.writerow([theory_id, theory_name, count])
                print(f"  {theory_name}: {count} papers")
    
    def run(self, initial_query: str, target_papers: int = 50, max_cost_usd: float = 100.0):
        """Run the agent"""
        
        print(f"""
╔══════════════════════════════════════════════════════════════╗
║   BIORXIV AGING RESEARCH AGENT                               ║
╚══════════════════════════════════════════════════════════════╝

Target Papers: {target_papers}
Budget: ${max_cost_usd}
Output Dir: {self.output_dir}

Starting...
""")
        
        # Search
        print(f"\n🔍 Searching BioRxiv: '{initial_query}'...")
        pmids = self.search_pubmed(initial_query, max_results=target_papers * 2)
        print(f"   Found {len(pmids)} candidates")
        
        # Process
        for i, pmid in enumerate(pmids[:target_papers], 1):
            print(f"\n\n📄 Paper {i}/{target_papers}")
            
            try:
                self.process_paper(pmid)
                
                if self.stats['total_cost'] >= max_cost_usd:
                    print(f"\n⚠️  Budget limit reached")
                    break
                    
            except KeyboardInterrupt:
                print("\n\n⚠️  Interrupted")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                continue
            
            time.sleep(0.5)
        
        # Finalize
        self.finalize_table1()
        
        # Stats
        runtime = time.time() - self.stats['start_time']
        print(f"""
╔══════════════════════════════════════════════════════════════╗
║                    COMPLETE!                                 ║
╚══════════════════════════════════════════════════════════════╝

Papers Processed: {self.stats['papers_processed']}
Full Text Retrieved: {self.stats['full_text_retrieved']}

Estimated Cost: ${self.stats['total_cost']:.2f}
Runtime: {runtime/60:.1f} minutes

SUBMISSION FILES:
  📊 {self.table1_file}
  📄 {self.table2_file}
  📝 {self.table3_file}

SUPPLEMENTARY FILES:
  🏷️  {self.theory_tags_file}
  📋 {self.metadata_file}
""")


def main():
    """Main entry point"""
    AGING_QUERIES_BIORXIV = [
        "aging",
        "senescence mechanisms",
        "aging biology",
        "longevity mechanisms",
        "age-related diseases",
        "biological aging",
        "hallmarks of aging",
        "aging theories",
        "oxidative stress aging",
        "reactive oxygen species aging",
        "ROS senescence",
        "antioxidants longevity",
        "free radicals aging",
        "telomere aging",
        "telomerase senescence",
        "telomere shortening",
        "mitochondrial dysfunction aging",
        "cellular senescence",
        "senescent cells",
        "senolytics",
        "stem cell exhaustion aging",
        "inflammaging",
        "proteostasis aging",
        "mTOR aging",
        "DNA damage aging",
        "epigenetic aging",
        "anti-aging interventions",
        "C elegans aging",
        "Drosophila aging",
        "mice aging",
        "naked mole rat longevity",
        "caloric restriction aging"
    ]

    agent = SubmissionAgent()
    for q in AGING_QUERIES_BIORXIV:
        agent.run(
            initial_query=q,
            target_papers=100000,
            max_cost_usd=1000.00
        )


if __name__ == "__main__":
    main()