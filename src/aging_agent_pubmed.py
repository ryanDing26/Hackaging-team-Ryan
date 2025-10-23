"""
Submission-Format Aging Research Agent
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
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

# Configuration
PUBMED_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"


@dataclass
class TheoryTag:
    """Theory tag with confidence score"""
    theory_id: int
    theory_name: str
    confidence: float
    evidence_snippets: List[str]
    source: str


class FullTextRetriever:
    """Retrieves full text from PubMed Central"""
    
    def __init__(self, email: str):
        self.email = email
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': f'AgingResearchBot/2.0 ({email})'})
    
    def get_full_text(self, pmid: str) -> Tuple[Optional[str], Optional[str]]:
        """Attempt to retrieve full text from PMC"""
        try:
            # Check if paper is in PMC
            link_url = f"{PUBMED_BASE_URL}elink.fcgi"
            params = {
                'dbfrom': 'pubmed',
                'id': pmid,
                'linkname': 'pubmed_pmc',
                'retmode': 'json'
            }
            
            response = self.session.get(link_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            pmc_id = None
            if 'linksets' in data and len(data['linksets']) > 0:
                linkset = data['linksets'][0]
                if 'linksetdbs' in linkset and len(linkset['linksetdbs']) > 0:
                    links = linkset['linksetdbs'][0].get('links', [])
                    if links:
                        pmc_id = f"PMC{links[0]}"
            
            if not pmc_id:
                return None, None
            
            # Fetch full text
            efetch_url = f"{PUBMED_BASE_URL}efetch.fcgi"
            params = {
                'db': 'pmc',
                'id': pmc_id,
                'rettype': 'xml',
                'retmode': 'xml'
            }
            
            response = self.session.get(efetch_url, params=params, timeout=30)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            sections = []
            
            for article in root.findall('.//article'):
                abstract = self._extract_text(article.find('.//abstract'))
                if abstract:
                    sections.append(f"ABSTRACT:\n{abstract}\n")
                
                body = article.find('.//body')
                if body:
                    for sec in body.findall('.//sec'):
                        title = self._extract_text(sec.find('.//title'))
                        content = self._extract_text(sec)
                        if title:
                            sections.append(f"\n{title.upper()}:\n{content}\n")
                        else:
                            sections.append(f"\n{content}\n")
            
            if sections:
                return "\n".join(sections), "pmc"
            
            return None, None
            
        except Exception as e:
            print(f"  Error retrieving full text: {e}")
            return None, None
    
    def _extract_text(self, element) -> str:
        if element is None:
            return ""
        return " ".join(element.itertext()).strip()


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
        """Search PubMed"""
        try:
            search_url = f"{PUBMED_BASE_URL}esearch.fcgi"
            params = {
                'db': 'pubmed',
                'term': query,
                'retmax': max_results,
                'retmode': 'json',
                'sort': 'relevance'
            }
            
            response = requests.get(search_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            return data.get('esearchresult', {}).get('idlist', [])
            
        except Exception as e:
            print(f"Error searching PubMed: {e}")
            return []
    
    def fetch_metadata(self, pmid: str) -> Optional[Dict]:
        """Fetch paper metadata"""
        try:
            fetch_url = f"{PUBMED_BASE_URL}efetch.fcgi"
            params = {
                'db': 'pubmed',
                'id': pmid,
                'retmode': 'xml'
            }
            
            response = requests.get(fetch_url, params=params, timeout=30)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            article = root.find('.//PubmedArticle')
            
            if article is None:
                return None
            
            medline = article.find('.//MedlineCitation')
            title_elem = medline.find('.//ArticleTitle')
            abstract_elem = medline.find('.//AbstractText')
            year_elem = medline.find('.//PubDate/Year')
            journal_elem = medline.find('.//Journal/Title')
            
            authors = []
            for author in medline.findall('.//Author'):
                last = author.find('LastName')
                first = author.find('ForeName')
                if last is not None:
                    name = last.text
                    if first is not None:
                        name = f"{first.text} {name}"
                    authors.append(name)
            
            return {
                'pmid': pmid,
                'title': title_elem.text if title_elem is not None else '',
                'abstract': abstract_elem.text if abstract_elem is not None else '',
                'year': int(year_elem.text) if year_elem is not None else 0,
                'authors': authors,
                'journal': journal_elem.text if journal_elem is not None else '',
                'url': f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
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
        print(f"Processing PMID: {pmid}")
        
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
║   SUBMISSION-FORMAT AGING RESEARCH AGENT                     ║
╚══════════════════════════════════════════════════════════════╝

Target Papers: {target_papers}
Budget: ${max_cost_usd}
Output Dir: {self.output_dir}

Starting...
""")
        
        # Search
        print(f"\n🔍 Searching: '{initial_query}'...")
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
    AGING_QUERIES = [
        # General Aging
        # "aging mechanisms[Title/Abstract]",
        "senescence mechanisms[Title/Abstract]",
        "aging biology[Title/Abstract]",
        "longevity[Title/Abstract] AND mechanisms",
        "age-related diseases[Title/Abstract]",
        "biological aging[Title/Abstract]",
        "hallmarks of aging[Title/Abstract]",
        "aging theories[Title/Abstract]",
        
        # Free Radical Theory
        "oxidative stress[Title/Abstract] AND aging",
        "reactive oxygen species[Title/Abstract] AND aging",
        "ROS[Title/Abstract] AND senescence",
        "antioxidants[Title/Abstract] AND longevity",
        "free radicals[Title/Abstract] AND aging",
        
        # Telomere Shortening
        "telomere[Title/Abstract] AND aging",
        "telomerase[Title/Abstract] AND senescence",
        "telomere shortening[Title/Abstract]",
        "telomere attrition[Title/Abstract]",
        "telomere length[Title/Abstract] AND longevity",
        
        # Mitochondrial Dysfunction
        "mitochondrial dysfunction[Title/Abstract] AND aging",
        "mitochondria[Title/Abstract] AND senescence",
        "mitochondrial decline[Title/Abstract]",
        "mitophagy[Title/Abstract] AND aging",
        "mitochondrial biogenesis[Title/Abstract] AND aging",
        
        # Cellular Senescence
        "cellular senescence[Title/Abstract]",
        "senescent cells[Title/Abstract]",
        "senolytics[Title/Abstract]",
        "SASP[Title/Abstract] AND aging",
        "senescence-associated secretory phenotype[Title/Abstract]",
        
        # Stem Cell Exhaustion
        "stem cell exhaustion[Title/Abstract]",
        "stem cell aging[Title/Abstract]",
        "stem cell decline[Title/Abstract]",
        "hematopoietic stem cells[Title/Abstract] AND aging",
        "regenerative capacity[Title/Abstract] AND aging",
        
        # Altered Intercellular Communication
        "intercellular communication[Title/Abstract] AND aging",
        "inflammaging[Title/Abstract]",
        "chronic inflammation[Title/Abstract] AND aging",
        "cytokines[Title/Abstract] AND senescence",
        "paracrine signaling[Title/Abstract] AND aging",
        
        # Loss of Proteostasis
        "proteostasis[Title/Abstract] AND aging",
        "protein aggregation[Title/Abstract] AND aging",
        "autophagy[Title/Abstract] AND senescence",
        "unfolded protein response[Title/Abstract] AND aging",
        "chaperones[Title/Abstract] AND aging",
        "proteasome[Title/Abstract] AND aging",
        
        # Deregulated Nutrient Sensing
        "mTOR[Title/Abstract] AND aging",
        "nutrient sensing[Title/Abstract] AND aging",
        "insulin signaling[Title/Abstract] AND longevity",
        "IGF-1[Title/Abstract] AND aging",
        "AMPK[Title/Abstract] AND aging",
        "caloric restriction[Title/Abstract]",
        
        # Genomic Instability
        "genomic instability[Title/Abstract] AND aging",
        "DNA damage[Title/Abstract] AND aging",
        "DNA repair[Title/Abstract] AND senescence",
        "chromosomal instability[Title/Abstract] AND aging",
        "mutation accumulation[Title/Abstract] AND aging",
        
        # Epigenetic Alterations
        "epigenetic alterations[Title/Abstract] AND aging",
        "DNA methylation[Title/Abstract] AND aging",
        "histone modifications[Title/Abstract] AND aging",
        "chromatin remodeling[Title/Abstract] AND aging",
        "epigenetic clock[Title/Abstract]",
        
        # Interventions
        "anti-aging interventions[Title/Abstract]",
        "longevity interventions[Title/Abstract]",
        "aging reversal[Title/Abstract]",
        
        # Model Organisms
        "aging[Title/Abstract] AND C elegans",
        "aging[Title/Abstract] AND Drosophila",
        "aging[Title/Abstract] AND mice",
        "longevity[Title/Abstract] AND naked mole rat",
        "aging[Title/Abstract] AND caloric restriction",
    ]
    agent = SubmissionAgent()
    for q in AGING_QUERIES:
        agent.run(
            initial_query=q,
            target_papers=100000,
            max_cost_usd=1000.00
        )


if __name__ == "__main__":
    main()