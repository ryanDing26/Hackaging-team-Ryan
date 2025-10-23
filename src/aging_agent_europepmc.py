"""
Submission-Format Aging Research Agent - Europe PMC Version (FIXED)
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
import urllib.parse

load_dotenv()

# Configuration - Europe PMC API
EPMC_BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest"


@dataclass
class TheoryTag:
    """Theory tag with confidence score"""
    theory_id: int
    theory_name: str
    confidence: float
    evidence_snippets: List[str]
    source: str


class FullTextRetriever:
    """Retrieve full text from Europe PMC"""
    
    def __init__(self, email: str):
        self.email = email
    
    def get_full_text(self, paper_id: str, source_type: str = "PMC") -> Tuple[Optional[str], Optional[str]]:
        """Attempt to retrieve full text from Europe PMC"""
        try:
            # Try multiple endpoints
            if source_type == "PMC":
                url = f"{EPMC_BASE_URL}/{paper_id}/fullTextXML"
            else:
                # For MED (PubMed) or other sources
                url = f"{EPMC_BASE_URL}/{source_type}/{paper_id}/fullTextXML"
            
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                text = response.text
                if len(text) > 1000:
                    return text[:100000], "europepmc"
            
            return None, None
            
        except Exception as e:
            return None, None


class SubmissionAgent:
    """Agent producing submission-format CSVs"""
    
    def __init__(
        self,
        anthropic_api_key: Optional[str] = None,
        pubmed_email: Optional[str] = None,
        output_dir: str = "europepmc_output"
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
        self.theory_papers = {}
        
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
    
    def search_pubmed(self, query: str, max_results: int = 100) -> List[Tuple[str, str]]:
        """
        Search Europe PMC and return a list of (paper_id, source_type) tuples.
        source_type can be 'PMC', 'MED', 'PPR', etc.
        """
        results = []
        page_size = 100  # max per request
        cursor_mark = "*"

        while len(results) < max_results:
            params = {
                "query": query,
                "format": "json",
                "resultType": "core",
                "pageSize": page_size,
                "cursorMark": cursor_mark
            }
            r = requests.get("https://www.ebi.ac.uk/europepmc/webservices/rest/search", params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            hits = data.get("resultList", {}).get("result", [])
            if not hits:
                break

            for hit in hits:
                paper_id = hit.get("id")
                source = hit.get("source", "MED")
                if paper_id:
                    results.append((paper_id, source))

            # Get the next cursor mark
            cursor_mark = data.get("nextCursorMark")
            if not cursor_mark:
                break

        return results[:max_results]

    
    def fetch_metadata(self, paper_id: str, source_type: str = "MED") -> Optional[Dict]:
        """Fetch detailed metadata for a paper from Europe PMC."""
        try:
            params = {"query": paper_id, "format": "json", "resultType": "core"}
            r = requests.get(f"{EPMC_BASE_URL}/search", params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            results = data.get("resultList", {}).get("result", [])
            if not results:
                return None

            paper = results[0]

            # Authors
            authors = []
            for a in paper.get("authorList", {}).get("author", [])[:10]:
                if a.get("fullName"):
                    authors.append(a["fullName"])

            # URL fallback
            if paper.get("pmcid"):
                url = f"https://europepmc.org/article/PMC/{paper['pmcid']}"
            elif paper.get("pmid"):
                url = f"https://pubmed.ncbi.nlm.nih.gov/{paper['pmid']}"
            elif paper.get("doi"):
                url = f"https://doi.org/{paper['doi']}"
            else:
                source = paper.get("source", "MED")
                url = f"https://europepmc.org/article/{source}/{paper.get('id', paper_id)}"

            return {
                "pmid": paper.get("pmid") or paper.get("id"),
                "pmcid": paper.get("pmcid"),
                "title": paper.get("title", ""),
                "abstract": paper.get("abstractText", ""),
                "authors": authors,
                "journal": paper.get("journalTitle", ""),
                "year": paper.get("pubYear", ""),
                "url": url,
                "source": paper.get("source", "MED")
            }
        except Exception as e:
            print(f"Metadata error: {e}")
            return None

    
    def tag_theories(self, pmid: str, title: str, text: str) -> List[TheoryTag]:
        """Tag paper with relevant aging theories using Claude"""
        
        prompt = f"""Analyze this aging research paper and identify which aging theories it relates to.

**Theories:**
1. Free Radical Theory
2. Telomere Shortening
3. Mitochondrial Dysfunction
4. Cellular Senescence
5. Stem Cell Exhaustion
6. Altered Intercellular Communication
7. Loss of Proteostasis
8. Deregulated Nutrient Sensing
9. Genomic Instability
10. Epigenetic Alterations

**Paper Title:** {title}

**Paper Text:** {text[:50000]}

For each relevant theory, provide:
- theory_id (1-10)
- confidence (0.0-1.0)
- evidence (brief quotes or descriptions)

Output JSON array:
[{{"theory_id": 1, "confidence": 0.9, "evidence": ["quote1", "quote2"]}}]"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            text_resp = response.content[0].text.strip()
            if '```' in text_resp:
                text_resp = text_resp.split('```')[1]
                if text_resp.startswith('json'):
                    text_resp = text_resp[4:]
            
            results = json.loads(text_resp.strip())
            
            theory_tags = []
            for result in results:
                theory_id = result.get('theory_id')
                if theory_id in self.theories:
                    theory_tags.append(TheoryTag(
                        theory_id=theory_id,
                        theory_name=self.theories[theory_id],
                        evidence_snippets=result.get('evidence', [])[:3],
                        source='abstract' if len(text) < 5000 else 'full_text'
                    ))
            
            if not theory_tags:
                theory_tags.append(TheoryTag(
                    theory_id=1,
                    theory_name=self.theories[1],
                    confidence=0.3,
                    evidence_snippets=["Default classification"],
                    source='default'
                ))
            
            return theory_tags
            
        except Exception as e:
            print(f"  Error tagging: {e}")
            return [TheoryTag(
                theory_id=1,
                theory_name=self.theories[1],
                confidence=0.3,
                evidence_snippets=["Error in processing"],
                source='error'
            )]
    
    def extract_answers(self, pmid: str, title: str, text: str) -> Dict[str, str]:
        """Extract answers to questions using Claude"""
        
        prompt = f"""Analyze this aging research paper and answer the following questions:

**Paper Title:** {title}

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
    
    def process_paper(self, paper_id: str, source_type: str = 'MED') -> bool:
        """Process single paper"""
        start_time = time.time()
        
        print(f"\n{'='*80}")
        print(f"Processing {source_type} ID: {paper_id}")
        
        print("Step 1: Fetching metadata...")
        metadata = self.fetch_metadata(paper_id, source_type)
        if not metadata:
            print("  ❌ Failed")
            return False
        print(f"  ✓ {metadata['title'][:60]}...")
        
        print("\nStep 2: Attempting full text...")
        full_text, source = self.full_text_retriever.get_full_text(paper_id, source_type)
        has_full_text = full_text is not None
        
        if has_full_text:
            print(f"  ✓ Retrieved from {source}")
            self.stats['full_text_retrieved'] += 1
            text = full_text
        else:
            print("  ⚠ Using abstract only")
            text = metadata['abstract']
        
        print("\nStep 3: Tagging theories...")
        theory_tags = self.tag_theories(paper_id, metadata['title'], text)
        print(f"  ✓ Found {len(theory_tags)} theories:")
        for tag in theory_tags:
            print(f"    - {tag.theory_name} ({tag.confidence:.2f})")
        
        print("\nStep 4: Extracting answers...")
        answers = self.extract_answers(paper_id, metadata['title'], text)
        print(f"  ✓ Q1-Q9 extracted")
        
        confidence = "high" if has_full_text else "medium"
        
        processing_time = time.time() - start_time
        print(f"\nOverall confidence: {confidence.upper()}")  # FIXED: changed UPPER() to upper()
        print(f"⏱ Processing time: {processing_time:.2f}s")
        
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
        
        primary_theory = max(theory_tags, key=lambda t: t.confidence)
        theory_id = primary_theory.theory_id
        
        if theory_id not in self.theory_papers:
            self.theory_papers[theory_id] = []
        self.theory_papers[theory_id].append(paper_url)
        
        with open(self.table2_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([theory_id, paper_url, paper_name, paper_year])
        
        with open(self.table3_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                theory_id, paper_url, paper_name, paper_year,
                answers['Q1'], answers['Q2'], answers['Q3'], answers['Q4'], answers['Q5'],
                answers['Q6'], answers['Q7'], answers['Q8'], answers['Q9']
            ])
        
        with open(self.theory_tags_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for tag in theory_tags:
                writer.writerow([
                    paper_url, tag.theory_id, tag.theory_name, f"{tag.confidence:.3f}",
                    " | ".join(tag.evidence_snippets[:2]), tag.source
                ])
        
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
║   EUROPE PMC AGING RESEARCH AGENT                            ║
╚══════════════════════════════════════════════════════════════╝

Target Papers: {target_papers}
Budget: ${max_cost_usd}
Output Dir: {self.output_dir}

Starting...
""")
        
        print(f"\n🔍 Searching Europe PMC: '{initial_query}'...")
        paper_ids = self.search_pubmed(initial_query, max_results=target_papers * 2)
        print(f"   Found {len(paper_ids)} candidates")
        
        if not paper_ids:
            print("\n⚠️  No papers found! Check your query or API connectivity.")
            print("   Tip: Try a simpler query like 'aging' or 'senescence'")
            return
        
        for i, (paper_id, source_type) in enumerate(paper_ids[:target_papers], 1):
            print(f"\n\n📄 Paper {i}/{target_papers}")
            
            try:
                self.process_paper(paper_id, source_type)
                
                if self.stats['total_cost'] >= max_cost_usd:
                    print(f"\n⚠️  Budget limit reached")
                    break
                    
            except KeyboardInterrupt:
                print("\n\n⚠️  Interrupted")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                import traceback
                traceback.print_exc()
                continue
            
            time.sleep(0.5)
        
        self.finalize_table1()
        
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
    AGING_QUERIES_EPMC = [
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
    for q in AGING_QUERIES_EPMC:
        agent.run(
            initial_query=q,
            target_papers=1000,
            max_cost_usd=1000.00
        )


if __name__ == "__main__":
    main()