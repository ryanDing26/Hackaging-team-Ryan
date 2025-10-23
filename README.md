# Multi-Agent Aging Theory Retrieval and QA System

Claude Sonnet-based model to collect and analyze aging research papers from a variety of biomedical databases.

## What It Does

The agent:
1. **Collects Papers** - Searches PubMed and fetches paper metadata
2. **Tags Papers** - Uses Claude to identify aging-related papers and theories based on full text or abstract
3. **Answers Questions** - Answers 9 specific questions about each paper
4. **Generates CSVs** - Outputs three CSV files with all collected data

## Output Files (per model)

### Table 1: `table1_theories.csv`
- `theory_id`: Unique theory identifier (e.g., T001, T002)
- `theory_name`: Name of the aging theory
- `number_of_collected_papers`: Number of papers for this theory

### Table 2: `table2_papers.csv`
- `theory_id`: Theory this paper relates to
- `paper_url`: PubMed URL
- `paper_name`: Paper title
- `paper_year`: Publication year

### Table 3: `table3_annotations.csv`
- `theory_id`, `paper_url`, `paper_name`, `paper_year`: Paper info
- `Q1` through `Q9`: Answers to the 9 research questions

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up API Key

Get your Anthropic API key from: https://console.anthropic.com/

```bash
export ANTHROPIC_API_KEY='your-api-key-here'
```

Optional: Set your email for PubMed (recommended for better rate limits):
```bash
export PUBMED_EMAIL='your_email@example.com'
```

### 3. Run the Agent

```bash
sbatch run_agent_[database type].sh
```

Database-agnostic agent setup.

## Project Structure

```
.
├── run_agent_pubmed.sh         # Main runner script(s)
├── run_agent_europepmc.sh      # Main runner script(s)
├── run_agent_arxiv.sh          # Main runner script(s)
├── run_agent_biorxiv.sh        # Main runner script(s)
├── run_agent_medrxiv.sh        # Main runner script(s)
├── .gitignore
├── .env                        # See above for how to configure
├── requirements.txt            # Python dependencies
├── src/
│   ├── aging_tools.py                    # Data structures and tool templates
│   ├── aging_tools_implementation.py     # API integrations (PubMed, etc.)
│   └── aging_workflow.py                 # Workflow orchestration
├── results/                    # Generated CSV files (preprocessed and aggregated)
│   ├── table1_theories.csv
│   ├── table2_papers.csv
│   └── table3_annotations.csv
```

## How It Works

```
┌─────────────────────────────────────────┐
│  1. OBTAIN QUERIES                      │
│     Claude performs new search queries  │
└─────────────┬───────────────────────────┘
              │
┌─────────────▼───────────────────────────┐
│  2. SEARCH PUBMED                       │
│     Execute queries and collect IDs     │
└─────────────┬───────────────────────────┘
              │
┌─────────────▼───────────────────────────┐
│  3. FETCH DETAILS                       │
│     Get titles, abstracts, metadata     │
└─────────────┬───────────────────────────┘
              │
┌─────────────▼───────────────────────────┐
│  4. CLASSIFY PAPERS                     │
│     Claude determines if aging-related  │
│     and assigns to theories             │
└─────────────┬───────────────────────────┘
              │
┌─────────────▼───────────────────────────┐
│  5. EXTRACT DATA                        │
│     Claude answers 9 questions          │
│     for each paper                      │
└─────────────┬───────────────────────────┘
              │
              └──────► Repeat until queries exhausted
```