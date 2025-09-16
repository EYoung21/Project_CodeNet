#!/usr/bin/env python3
"""
Script to extract all coding problems from Project CodeNet repository
Extracts structured information from HTML problem descriptions
"""

import os
import json
import re
from bs4 import BeautifulSoup
from pathlib import Path
import sys

def clean_html_text(html_content):
    """Clean HTML content and extract plain text"""
    if not html_content:
        return ""
    
    # Parse HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove script and style elements
    for script in soup(["script", "style"]):
        script.decompose()
    
    # Get text and clean it
    text = soup.get_text()
    
    # Clean up whitespace
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = ' '.join(chunk for chunk in chunks if chunk)
    
    return text

def extract_sections_from_html(html_content):
    """Extract structured sections from HTML problem description"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    sections = {}
    
    # Extract title
    title_tag = soup.find('h1')
    if title_tag:
        sections['title'] = clean_html_text(str(title_tag))
    
    # Extract problem description (everything before first H2)
    description_parts = []
    current = title_tag.next_sibling if title_tag else soup.find('body')
    
    while current:
        if hasattr(current, 'name') and current.name and current.name.lower() == 'h2':
            break
        if hasattr(current, 'get_text'):
            text = current.get_text().strip()
            if text:
                description_parts.append(text)
        elif isinstance(current, str) and current.strip():
            description_parts.append(current.strip())
        current = current.next_sibling
    
    sections['description'] = ' '.join(description_parts)
    
    # Extract all H2 sections
    h2_tags = soup.find_all('h2')
    current_section = None
    
    for h2 in h2_tags:
        section_name = clean_html_text(str(h2)).lower()
        sections[section_name] = ""
        
        # Get content until next H2 or end
        current = h2.next_sibling
        content_parts = []
        
        while current:
            if hasattr(current, 'name') and current.name and current.name.lower() == 'h2':
                break
            if hasattr(current, 'get_text'):
                text = current.get_text().strip()
                if text:
                    content_parts.append(text)
            elif isinstance(current, str) and current.strip():
                content_parts.append(current.strip())
            current = current.next_sibling
        
        sections[section_name] = ' '.join(content_parts)
    
    return sections

def extract_examples_from_sections(sections):
    """Extract input/output examples from sections"""
    examples = {"sampleCases": [], "testCases": []}
    
    # Look for sample input/output pairs
    sample_input_keys = [k for k in sections.keys() if 'sample input' in k.lower()]
    sample_output_keys = [k for k in sections.keys() if ('output for' in k.lower() or 'sample output' in k.lower())]
    
    # Pair up inputs and outputs
    for i, input_key in enumerate(sample_input_keys):
        input_text = sections.get(input_key, "").strip()
        
        # Find corresponding output
        output_text = ""
        if i < len(sample_output_keys):
            output_text = sections.get(sample_output_keys[i], "").strip()
        
        if input_text or output_text:
            examples["sampleCases"].append({
                "input": input_text,
                "output": output_text,
                "explanation": ""
            })
    
    return examples

def extract_constraints_from_sections(sections):
    """Extract constraints from sections"""
    constraints = {
        "timeLimit": None,
        "memoryLimit": None,
        "inputConstraints": {
            "description": "",
            "ranges": ""
        },
        "languageRestrictions": []
    }
    
    # Look for constraints section
    constraints_text = ""
    for key, value in sections.items():
        if 'constraint' in key.lower():
            constraints_text = value
            break
    
    if constraints_text:
        constraints["inputConstraints"]["description"] = constraints_text
        
        # Try to extract ranges using regex
        range_patterns = [
            r'(\d+)\s*[≤<=]\s*\w+\s*[≤<=]\s*(\d+)',
            r'\w+\s*[≤<=]\s*(\d+)',
            r'(\d+)\s*[≤<=]\s*\w+'
        ]
        
        ranges = []
        for pattern in range_patterns:
            matches = re.findall(pattern, constraints_text)
            ranges.extend([' '.join(match) if isinstance(match, tuple) else str(match) for match in matches])
        
        if ranges:
            constraints["inputConstraints"]["ranges"] = '; '.join(ranges)
    
    return constraints

def assess_difficulty(sections, problem_id):
    """Assess problem difficulty based on content analysis"""
    description = sections.get('description', '') + ' ' + sections.get('title', '')
    description_lower = description.lower()
    
    # Simple heuristics for difficulty assessment
    easy_indicators = ['sum', 'count', 'simple', 'basic', 'digit', 'triangle', 'maximum', 'minimum']
    medium_indicators = ['algorithm', 'sort', 'search', 'tree', 'graph', 'dynamic', 'optimization']
    hard_indicators = ['complex', 'advanced', 'polynomial', 'np-hard', 'exponential', 'combinatorial']
    
    easy_score = sum(1 for indicator in easy_indicators if indicator in description_lower)
    medium_score = sum(1 for indicator in medium_indicators if indicator in description_lower)
    hard_score = sum(1 for indicator in hard_indicators if indicator in description_lower)
    
    # Also consider problem ID (later problems tend to be harder)
    problem_num = int(problem_id[1:]) if problem_id[1:].isdigit() else 0
    
    if hard_score > 0 or problem_num > 3000:
        return "Hard"
    elif medium_score > easy_score or problem_num > 1000:
        return "Medium"
    else:
        return "Easy"

def categorize_problem(sections):
    """Categorize problem based on content"""
    content = (sections.get('description', '') + ' ' + sections.get('title', '')).lower()
    
    # Category mapping based on keywords
    categories = {
        'Arrays & Strings': ['array', 'string', 'text', 'character', 'sequence'],
        'Math & Logic': ['math', 'number', 'digit', 'calculate', 'formula', 'equation'],
        'Geometry': ['triangle', 'circle', 'coordinate', 'distance', 'angle', 'geometry'],
        'Sorting & Searching': ['sort', 'search', 'find', 'order', 'binary search'],
        'Dynamic Programming': ['dynamic', 'dp', 'optimization', 'maximum', 'minimum'],
        'Trees & Graphs': ['tree', 'graph', 'node', 'edge', 'path', 'traversal'],
        'Greedy Algorithms': ['greedy', 'optimal', 'choice'],
        'Simulation': ['simulate', 'game', 'step', 'process'],
        'Implementation': ['implement', 'program', 'algorithm']
    }
    
    best_category = 'Implementation'  # default
    max_score = 0
    
    for category, keywords in categories.items():
        score = sum(1 for keyword in keywords if keyword in content)
        if score > max_score:
            max_score = score
            best_category = category
    
    return best_category

def generate_code_template(sections, language):
    """Generate basic code template for the problem"""
    templates = {
        'python': '''def solve():
    # Read input
    # Process data
    # Output result
    pass

if __name__ == "__main__":
    solve()''',
        
        'cpp': '''#include <iostream>
#include <vector>
#include <string>
using namespace std;

int main() {
    // Read input
    // Process data
    // Output result
    return 0;
}''',
        
        'java': '''import java.util.*;
import java.io.*;

public class Solution {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        // Read input
        // Process data
        // Output result
        sc.close();
    }
}''',
        
        'javascript': '''function solve() {
    // Read input
    // Process data
    // Output result
}

solve();'''
    }
    
    return templates.get(language, templates['python'])

def extract_problem_from_html_file(file_path):
    """Extract a single problem from HTML file"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            html_content = f.read()
        
        if not html_content.strip():
            return None
        
        # Extract problem ID from filename
        problem_id = Path(file_path).stem
        
        # Parse HTML and extract sections
        sections = extract_sections_from_html(html_content)
        
        if not sections.get('title'):
            return None
        
        # Extract structured information
        examples = extract_examples_from_sections(sections)
        constraints = extract_constraints_from_sections(sections)
        difficulty = assess_difficulty(sections, problem_id)
        category = categorize_problem(sections)
        
        # Generate tags
        tags = []
        content_lower = (sections.get('description', '') + ' ' + sections.get('title', '')).lower()
        
        tag_keywords = {
            'array': ['array', 'list'],
            'string': ['string', 'text', 'character'],
            'math': ['math', 'number', 'calculation'],
            'geometry': ['triangle', 'circle', 'coordinate'],
            'sorting': ['sort', 'order'],
            'graph': ['graph', 'tree', 'node'],
            'simulation': ['simulate', 'game'],
            'implementation': ['implement', 'program']
        }
        
        for tag, keywords in tag_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                tags.append(tag)
        
        if not tags:
            tags = ['implementation']
        
        # Build problem object
        problem = {
            "basicInfo": {
                "questionId": problem_id,
                "title": sections.get('title', f"Problem {problem_id}").replace('Problem F: ', '').replace('Problem A: ', ''),
                "description": sections.get('description', ''),
                "difficulty": difficulty,
                "category": category,
                "tags": tags,
                "source": str(file_path)
            },
            "constraints": constraints,
            "examples": examples,
            "codeTemplates": {
                "python": generate_code_template(sections, 'python'),
                "cpp": generate_code_template(sections, 'cpp'),
                "java": generate_code_template(sections, 'java'),
                "javascript": generate_code_template(sections, 'javascript')
            },
            "metadata": {
                "extractedFrom": str(file_path),
                "confidence": 0.8 if sections.get('description') and examples["sampleCases"] else 0.6,
                "notes": f"Extracted from Project CodeNet problem {problem_id}"
            }
        }
        
        return problem
        
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None

def main():
    """Main function to extract all problems"""
    # Find problem descriptions directory
    base_dir = Path(__file__).parent
    problems_dir = base_dir / "doc" / "problem_descriptions"
    
    if not problems_dir.exists():
        print(f"Problem descriptions directory not found: {problems_dir}")
        return
    
    print(f"Extracting problems from: {problems_dir}")
    
    # Get all HTML files
    html_files = list(problems_dir.glob("p*.html"))
    print(f"Found {len(html_files)} problem files")
    
    problems = []
    processed = 0
    
    for html_file in sorted(html_files):
        if processed % 100 == 0:
            print(f"Processed {processed}/{len(html_files)} problems...")
        
        problem = extract_problem_from_html_file(html_file)
        if problem:
            problems.append(problem)
        
        processed += 1
    
    print(f"Successfully extracted {len(problems)} problems")
    
    # Create output JSON
    output = {"problems": problems}
    
    # Write to file
    output_file = base_dir / "extracted_problems.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"Saved all problems to: {output_file}")
    print(f"Total problems extracted: {len(problems)}")
    
    # Print summary statistics
    difficulties = {}
    categories = {}
    
    for problem in problems:
        diff = problem["basicInfo"]["difficulty"]
        cat = problem["basicInfo"]["category"]
        
        difficulties[diff] = difficulties.get(diff, 0) + 1
        categories[cat] = categories.get(cat, 0) + 1
    
    print("\nDifficulty distribution:")
    for diff, count in sorted(difficulties.items()):
        print(f"  {diff}: {count}")
    
    print("\nCategory distribution:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")

if __name__ == "__main__":
    main()
