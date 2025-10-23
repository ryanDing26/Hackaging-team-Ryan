"""
Submission-Format Aging Research Agent - arXiv Version
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
import xml.etree.ElementTree as ET

load_dotenv()

# Configuration - arXiv API
ARXIV_BASE_URL = "http://export.arxiv.org/api/query"


@dataclass
class TheoryTag:
    """Theory tag with confidence score"""
    theory_id: int
    theory_name: str
    confidence: float
    evidence_snippets: List[str]
    source: str


class FullTextRetriever:
    """Placeholder - arXiv doesn't provide full text via API"""
    
    def __init__(self, email: str):
        self.email = email
    
    def get_full_text(self, arxiv_id: str) -> Tuple[Optional[str], Optional[str]]:
        """arXiv doesn't provide full text via API"""
        return None, None


class SubmissionAgent:
    """Agent producing submission-format CSVs"""
    
    def __init__(
        self,
        anthropic_api_key: Optional[str] = None,
        pubmed_email: Optional[str] = None,
        output_dir: str = "arxiv_output"
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
    
    def search_pubmed(self, query: str, max_results: int = 100) -> List[str]:
        """Search arXiv - returns arXiv IDs"""
        try:
            # Clean query - remove PubMed syntax
            clean_query = query.replace('[Title/Abstract]', '').replace('[Title]', '').replace('[Abstract]', '').strip()
            
            # arXiv search query format
            # Search in q-bio (quantitative biology) category
            search_query = f'all:{clean_query} AND cat:q-bio*'
            
            params = {
                'search_query': search_query,
                'start': 0,
                'max_results': max_results,
                'sortBy': 'relevance',
                'sortOrder': 'descending'
            }
            
            response = requests.get(ARXIV_BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            
            arxiv_ids = []
            for entry in root.findall('atom:entry', ns):
                id_elem = entry.find('atom:id', ns)
                if id_elem is not None:
                    # Extract arXiv ID from URL like http://arxiv.org/abs/2301.12345v1
                    arxiv_id = id_elem.text.split('/abs/')[-1]
                    # Remove version number if present
                    if 'v' in arxiv_id:
                        arxiv_id = arxiv_id.split('v')[0]
                    arxiv_ids.append(arxiv_id)
            
            return arxiv_ids
            
        except Exception as e:
            print(f"Error searching arXiv: {e}")
            return []
    
    def fetch_metadata(self, pmid: str) -> Optional[Dict]:
        """Fetch paper metadata from arXiv - pmid is actually an arXiv ID"""
        try:
            params = {
                'id_list': pmid,
                'max_results': 1
            }
            
            response = requests.get(ARXIV_BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            
            entry = root.find('atom:entry', ns)
            if entry is None:
                return None
            
            title = entry.find('atom:title', ns).text.strip()
            summary = entry.find('atom:summary', ns).text.strip()
            published = entry.find('atom:published', ns).text[:4]
            
            authors = []
            for author in entry.findall('atom:author', ns):
                name = author.find('atom:name', ns).text
                authors.append(name)
            
            return {
                'pmid': pmid,
                'title': title,
                'abstract': summary,
                'year': int(published) if published else 0,
                'authors': authors,
                'journal': 'arXiv',
                'url': f"https://arxiv.org/abs/{pmid}"
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
        print(f"Processing arXiv ID: {pmid}")
        
        print("Step 1: Fetching metadata...")
        metadata = self.fetch_metadata(pmid)
        if not metadata:
            print("  ❌ Failed")
            return False
        print(f"  ✓ {metadata['title'][:60]}...")
        
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
        
        print("\nStep 3: Tagging theories...")
        theory_tags = self.tag_theories(pmid, metadata['title'], text)
        print(f"  ✓ Found {len(theory_tags)} theories:")
        for tag in theory_tags:
            print(f"    - {tag.theory_name} ({tag.confidence:.2f})")
        
        print("\nStep 4: Extracting answers...")
        answers = self.extract_answers(pmid, metadata['title'], text)
        print(f"  ✓ Q1-Q9 extracted")
        
        confidence = "high" if has_full_text else "medium"
        
        processing_time = time.time() - start_time
        print(f"\nOverall confidence: {confidence.upper()}")
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
║   ARXIV AGING RESEARCH AGENT                                 ║
╚══════════════════════════════════════════════════════════════╝

Target Papers: {target_papers}
Budget: ${max_cost_usd}
Output Dir: {self.output_dir}

Starting...
""")
        
        print(f"\n🔍 Searching arXiv: '{initial_query}'...")
        pmids = self.search_pubmed(initial_query, max_results=target_papers * 2)
        print(f"   Found {len(pmids)} candidates")
        
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
    AGING_QUERIES_ARXIV = [
        # General Aging
        'aging',
        '(ti:"senescence mechanisms" OR abs:"senescence mechanisms") AND cat:q-bio.*',
        '(ti:"aging biology" OR abs:"aging biology") AND cat:q-bio.*',
        '(ti:longevity OR abs:longevity) AND (ti:mechanisms OR abs:mechanisms) AND cat:q-bio.*',
        '(ti:"age-related diseases" OR abs:"age-related diseases") AND cat:q-bio.*',
        '(ti:"biological aging" OR abs:"biological aging") AND cat:q-bio.*',
        '(ti:"hallmarks of aging" OR abs:"hallmarks of aging") AND cat:q-bio.*',
        '(ti:"aging theories" OR abs:"aging theories") AND cat:q-bio.*',
        
        # Free Radical Theory
        '(ti:"oxidative stress" OR abs:"oxidative stress") AND (ti:aging OR abs:aging) AND cat:q-bio.*',
        '(ti:"reactive oxygen species" OR abs:"reactive oxygen species") AND (ti:aging OR abs:aging) AND cat:q-bio.*',
        '(ti:ROS OR abs:ROS) AND (ti:senescence OR abs:senescence) AND cat:q-bio.*',
        '(ti:antioxidants OR abs:antioxidants) AND (ti:longevity OR abs:longevity) AND cat:q-bio.*',
        '(ti:"free radicals" OR abs:"free radicals") AND (ti:aging OR abs:aging) AND cat:q-bio.*',
        
        # Telomere Shortening
        '(ti:telomere OR abs:telomere) AND (ti:aging OR abs:aging) AND cat:q-bio.*',
        '(ti:telomerase OR abs:telomerase) AND (ti:senescence OR abs:senescence) AND cat:q-bio.*',
        '(ti:"telomere shortening" OR abs:"telomere shortening") AND cat:q-bio.*',
        '(ti:"telomere attrition" OR abs:"telomere attrition") AND cat:q-bio.*',
        '(ti:"telomere length" OR abs:"telomere length") AND (ti:longevity OR abs:longevity) AND cat:q-bio.*',
        
        # Mitochondrial Dysfunction
        '(ti:"mitochondrial dysfunction" OR abs:"mitochondrial dysfunction") AND (ti:aging OR abs:aging) AND cat:q-bio.*',
        '(ti:mitochondria OR abs:mitochondria) AND (ti:senescence OR abs:senescence) AND cat:q-bio.*',
        '(ti:"mitochondrial decline" OR abs:"mitochondrial decline") AND cat:q-bio.*',
        '(ti:mitophagy OR abs:mitophagy) AND (ti:aging OR abs:aging) AND cat:q-bio.*',
        '(ti:"mitochondrial biogenesis" OR abs:"mitochondrial biogenesis") AND (ti:aging OR abs:aging) AND cat:q-bio.*',
        
        # Cellular Senescence
        '(ti:"cellular senescence" OR abs:"cellular senescence") AND cat:q-bio.*',
        '(ti:"senescent cells" OR abs:"senescent cells") AND cat:q-bio.*',
        '(ti:senolytics OR abs:senolytics) AND cat:q-bio.*',
        '(ti:SASP OR abs:SASP) AND (ti:aging OR abs:aging) AND cat:q-bio.*',
        '(ti:"senescence-associated secretory phenotype" OR abs:"senescence-associated secretory phenotype") AND cat:q-bio.*',
        
        # Stem Cell Exhaustion
        '(ti:"stem cell exhaustion" OR abs:"stem cell exhaustion") AND cat:q-bio.*',
        '(ti:"stem cell aging" OR abs:"stem cell aging") AND cat:q-bio.*',
        '(ti:"stem cell decline" OR abs:"stem cell decline") AND cat:q-bio.*',
        '(ti:"hematopoietic stem cells" OR abs:"hematopoietic stem cells") AND (ti:aging OR abs:aging) AND cat:q-bio.*',
        '(ti:"regenerative capacity" OR abs:"regenerative capacity") AND (ti:aging OR abs:aging) AND cat:q-bio.*',
        
        # Altered Intercellular Communication
        '(ti:"intercellular communication" OR abs:"intercellular communication") AND (ti:aging OR abs:aging) AND cat:q-bio.*',
        '(ti:inflammaging OR abs:inflammaging) AND cat:q-bio.*',
        '(ti:"chronic inflammation" OR abs:"chronic inflammation") AND (ti:aging OR abs:aging) AND cat:q-bio.*',
        '(ti:cytokines OR abs:cytokines) AND (ti:senescence OR abs:senescence) AND cat:q-bio.*',
        '(ti:"paracrine signaling" OR abs:"paracrine signaling") AND (ti:aging OR abs:aging) AND cat:q-bio.*',
        
        # Loss of Proteostasis
        '(ti:proteostasis OR abs:proteostasis) AND (ti:aging OR abs:aging) AND cat:q-bio.*',
        '(ti:"protein aggregation" OR abs:"protein aggregation") AND (ti:aging OR abs:aging) AND cat:q-bio.*',
        '(ti:autophagy OR abs:autophagy) AND (ti:senescence OR abs:senescence) AND cat:q-bio.*',
        '(ti:"unfolded protein response" OR abs:"unfolded protein response") AND (ti:aging OR abs:aging) AND cat:q-bio.*',
        '(ti:chaperones OR abs:chaperones) AND (ti:aging OR abs:aging) AND cat:q-bio.*',
        '(ti:proteasome OR abs:proteasome) AND (ti:aging OR abs:aging) AND cat:q-bio.*',
        
        # Deregulated Nutrient Sensing
        '(ti:mTOR OR abs:mTOR) AND (ti:aging OR abs:aging) AND cat:q-bio.*',
        '(ti:"nutrient sensing" OR abs:"nutrient sensing") AND (ti:aging OR abs:aging) AND cat:q-bio.*',
        '(ti:"insulin signaling" OR abs:"insulin signaling") AND (ti:longevity OR abs:longevity) AND cat:q-bio.*',
        '(ti:"IGF-1" OR abs:"IGF-1") AND (ti:aging OR abs:aging) AND cat:q-bio.*',
        '(ti:AMPK OR abs:AMPK) AND (ti:aging OR abs:aging) AND cat:q-bio.*',
        '(ti:"caloric restriction" OR abs:"caloric restriction") AND cat:q-bio.*',
        
        # Genomic Instability
        '(ti:"genomic instability" OR abs:"genomic instability") AND (ti:aging OR abs:aging) AND cat:q-bio.*',
        '(ti:"DNA damage" OR abs:"DNA damage") AND (ti:aging OR abs:aging) AND cat:q-bio.*',
        '(ti:"DNA repair" OR abs:"DNA repair") AND (ti:senescence OR abs:senescence) AND cat:q-bio.*',
        '(ti:"chromosomal instability" OR abs:"chromosomal instability") AND (ti:aging OR abs:aging) AND cat:q-bio.*',
        '(ti:"mutation accumulation" OR abs:"mutation accumulation") AND (ti:aging OR abs:aging) AND cat:q-bio.*',
        
        # Epigenetic Alterations
        '(ti:"epigenetic alterations" OR abs:"epigenetic alterations") AND (ti:aging OR abs:aging) AND cat:q-bio.*',
        '(ti:"DNA methylation" OR abs:"DNA methylation") AND (ti:aging OR abs:aging) AND cat:q-bio.*',
        '(ti:"histone modifications" OR abs:"histone modifications") AND (ti:aging OR abs:aging) AND cat:q-bio.*',
        '(ti:"chromatin remodeling" OR abs:"chromatin remodeling") AND (ti:aging OR abs:aging) AND cat:q-bio.*',
        '(ti:"epigenetic clock" OR abs:"epigenetic clock") AND cat:q-bio.*',
        
        # Interventions
        '(ti:"anti-aging interventions" OR abs:"anti-aging interventions") AND cat:q-bio.*',
        '(ti:"longevity interventions" OR abs:"longevity interventions") AND cat:q-bio.*',
        '(ti:"aging reversal" OR abs:"aging reversal") AND cat:q-bio.*',
        
        # Model Organisms
        '(ti:aging OR abs:aging) AND (ti:"C elegans" OR abs:"C elegans") AND cat:q-bio.*',
        '(ti:aging OR abs:aging) AND (ti:Drosophila OR abs:Drosophila) AND cat:q-bio.*',
        '(ti:aging OR abs:aging) AND (ti:mice OR abs:mice) AND cat:q-bio.*',
        '(ti:longevity OR abs:longevity) AND (ti:"naked mole rat" OR abs:"naked mole rat") AND cat:q-bio.*',
        '(ti:aging OR abs:aging) AND (ti:"caloric restriction" OR abs:"caloric restriction") AND cat:q-bio.*'
    ]

    agent = SubmissionAgent()
    for q in AGING_QUERIES_ARXIV:
        agent.run(
            initial_query=q,
            target_papers=1000,
            max_cost_usd=1000.00
        )


if __name__ == "__main__":
    main()