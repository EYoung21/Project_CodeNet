#!/usr/bin/env python3
"""
Improved script to extract ALL coding problems from Project CodeNet repository
Handles various HTML structures and edge cases
"""

import os
import json
import re
from bs4 import BeautifulSoup, Comment
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

def extract_from_comments(soup):
    """Extract content from HTML comments"""
    comments = soup.find_all(string=lambda text: isinstance(text, Comment))
    comment_content = []
    
    for comment in comments:
        # Parse comment content as HTML
        try:
            comment_soup = BeautifulSoup(comment, 'html.parser')
            text = clean_html_text(str(comment_soup))
            if text and len(text) > 20:  # Only meaningful content
                comment_content.append(text)
        except:
            pass
    
    return ' '.join(comment_content)

def extract_title_flexible(soup):
    """Extract title using multiple strategies"""
    # Strategy 1: H1 tag
    title_tag = soup.find('h1')
    if title_tag and title_tag.get_text().strip():
        return clean_html_text(str(title_tag))
    
    # Strategy 2: Problem Statement section (AtCoder style)
    problem_section = soup.find('h3', string='Problem Statement')
    if problem_section:
        # Look for title in nearby content
        parent = problem_section.parent
        if parent:
            title_text = parent.get_text().strip()
            lines = title_text.split('\n')
            for line in lines:
                if line.strip() and 'Problem Statement' not in line and len(line.strip()) < 100:
                    return line.strip()
    
    # Strategy 3: Look for any heading-like content
    for tag in soup.find_all(['h1', 'h2', 'h3', 'title']):
        text = tag.get_text().strip()
        if text and len(text) < 100 and text not in ['Input', 'Output', 'Constraints', 'Sample Input', 'Sample Output']:
            return text
    
    # Strategy 4: Extract from comments
    comment_content = extract_from_comments(soup)
    if comment_content:
        # Try to find a title-like line
        lines = comment_content.split('。')  # Split on Japanese period
        for line in lines[:3]:  # Check first few sentences
            if line.strip() and len(line.strip()) < 200:
                return line.strip()
    
    return ""

def extract_sections_from_html_improved(html_content):
    """Extract structured sections with improved handling"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    sections = {}
    
    # Extract title with flexible approach
    title = extract_title_flexible(soup)
    if title:
        sections['title'] = title
    
    # Extract problem description
    description_parts = []
    
    # Strategy 1: Look for content between title and first section
    first_section = soup.find(['h2', 'h3'], string=re.compile(r'(Input|Constraints|入力|制約)', re.I))
    if first_section:
        current = soup.find('body') if soup.find('body') else soup
        for element in current.find_all(['p', 'div']):
            if element.get_text().strip() and not any(section_word in element.get_text() for section_word in ['Input', 'Output', 'Constraints', 'Sample']):
                description_parts.append(element.get_text().strip())
    
    # Strategy 2: Extract from comments if main content is sparse
    if len(' '.join(description_parts)) < 50:
        comment_content = extract_from_comments(soup)
        if comment_content:
            description_parts.append(comment_content)
    
    # Strategy 3: Look for Problem Statement section (AtCoder)
    problem_statement = soup.find('h3', string='Problem Statement')
    if problem_statement:
        next_section = problem_statement.find_next(['h3', 'hr'])
        current = problem_statement.next_sibling
        while current and current != next_section:
            if hasattr(current, 'get_text') and current.get_text().strip():
                description_parts.append(current.get_text().strip())
            current = current.next_sibling
    
    sections['description'] = ' '.join(description_parts)
    
    # Extract standard sections with multiple language support
    section_mappings = {
        'input': ['Input', '入力', 'input'],
        'output': ['Output', '出力', 'output'],
        'constraints': ['Constraints', '制約', 'constraints'],
        'sample input': ['Sample Input', 'Sample Input 1', '入力例', 'sample input'],
        'sample output': ['Sample Output', 'Sample Output 1', '出力例', 'sample output'],
    }
    
    # Find sections by various headers
    for section_key, possible_names in section_mappings.items():
        for name in possible_names:
            # Look for h2, h3 tags
            header = soup.find(['h2', 'h3'], string=re.compile(re.escape(name), re.I))
            if header:
                content_parts = []
                current = header.next_sibling
                
                # Get content until next header
                while current:
                    if hasattr(current, 'name') and current.name and current.name.lower() in ['h2', 'h3']:
                        break
                    if hasattr(current, 'get_text'):
                        text = current.get_text().strip()
                        if text:
                            content_parts.append(text)
                    current = current.next_sibling
                
                if content_parts:
                    sections[section_key] = ' '.join(content_parts)
                    break
    
    return sections

def extract_examples_improved(sections):
    """Extract examples with improved parsing"""
    examples = {"sampleCases": [], "testCases": []}
    
    # Look for input/output pairs
    input_text = sections.get('sample input', sections.get('input', ''))
    output_text = sections.get('sample output', sections.get('output', ''))
    
    if input_text and output_text:
        examples["sampleCases"].append({
            "input": input_text.strip(),
            "output": output_text.strip(),
            "explanation": ""
        })
    
    return examples

def assess_difficulty_improved(sections, problem_id):
    """Improved difficulty assessment"""
    content = ' '.join([
        sections.get('title', ''),
        sections.get('description', ''),
        sections.get('constraints', '')
    ]).lower()
    
    # Problem ID based assessment (later problems tend to be harder)
    problem_num = int(problem_id[1:]) if problem_id[1:].isdigit() else 0
    
    # Keyword-based assessment
    easy_keywords = ['sum', 'count', 'simple', 'basic', 'digit', 'print', 'calculate', 'find']
    medium_keywords = ['algorithm', 'sort', 'search', 'tree', 'graph', 'dynamic', 'optimal', 'sequence']
    hard_keywords = ['complex', 'advanced', 'polynomial', 'exponential', 'combinatorial', 'optimization']
    
    easy_score = sum(1 for kw in easy_keywords if kw in content)
    medium_score = sum(1 for kw in medium_keywords if kw in content)
    hard_score = sum(1 for kw in hard_keywords if kw in content)
    
    # Constraint-based assessment
    constraints_text = sections.get('constraints', '')
    if '10^9' in constraints_text or '10^8' in constraints_text:
        hard_score += 2
    elif '10^6' in constraints_text or '10^5' in constraints_text:
        medium_score += 1
    
    # Final assessment
    if hard_score > 0 or problem_num > 3500:
        return "Hard"
    elif medium_score > easy_score or problem_num > 2000:
        return "Medium"
    else:
        return "Easy"

def categorize_problem_improved(sections):
    """Improved problem categorization"""
    content = ' '.join([
        sections.get('title', ''),
        sections.get('description', '')
    ]).lower()
    
    # Enhanced category detection
    categories = {
        'Arrays & Strings': ['array', 'string', 'text', 'character', 'sequence', 'list'],
        'Math & Logic': ['math', 'number', 'digit', 'calculate', 'formula', 'equation', 'arithmetic'],
        'Geometry': ['triangle', 'circle', 'coordinate', 'distance', 'angle', 'geometry', 'point'],
        'Sorting & Searching': ['sort', 'search', 'find', 'order', 'binary search', 'maximum', 'minimum'],
        'Dynamic Programming': ['dynamic', 'dp', 'optimization', 'optimal', 'recursive'],
        'Trees & Graphs': ['tree', 'graph', 'node', 'edge', 'path', 'traversal', 'connected'],
        'Greedy Algorithms': ['greedy', 'optimal choice', 'interval'],
        'Simulation': ['simulate', 'game', 'step', 'process', 'move'],
        'Implementation': ['implement', 'program', 'algorithm', 'output', 'print']
    }
    
    best_category = 'Implementation'
    max_score = 0
    
    for category, keywords in categories.items():
        score = sum(1 for keyword in keywords if keyword in content)
        if score > max_score:
            max_score = score
            best_category = category
    
    return best_category

def extract_problem_improved(file_path):
    """Extract problem with improved handling of edge cases"""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            html_content = f.read()
        
        if not html_content.strip():
            return None
        
        problem_id = Path(file_path).stem
        
        # Parse with improved extraction
        sections = extract_sections_from_html_improved(html_content)
        
        # Require at least some content
        if not sections.get('title') and not sections.get('description'):
            return None
        
        # Use problem ID as title if no title found
        if not sections.get('title'):
            sections['title'] = f"Problem {problem_id}"
        
        # Extract other components
        examples = extract_examples_improved(sections)
        difficulty = assess_difficulty_improved(sections, problem_id)
        category = categorize_problem_improved(sections)
        
        # Generate tags
        tags = []
        content_lower = (sections.get('description', '') + ' ' + sections.get('title', '')).lower()
        
        tag_keywords = {
            'array': ['array', 'list', 'sequence'],
            'string': ['string', 'text', 'character'],
            'math': ['math', 'number', 'calculation', 'arithmetic'],
            'geometry': ['triangle', 'circle', 'coordinate', 'geometry'],
            'sorting': ['sort', 'order', 'maximum', 'minimum'],
            'graph': ['graph', 'tree', 'node', 'path'],
            'simulation': ['simulate', 'game', 'process'],
            'implementation': ['implement', 'program', 'output']
        }
        
        for tag, keywords in tag_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                tags.append(tag)
        
        if not tags:
            tags = ['implementation']
        
        # Build constraints
        constraints = {
            "timeLimit": None,
            "memoryLimit": None,
            "inputConstraints": {
                "description": sections.get('constraints', ''),
                "ranges": ""
            },
            "languageRestrictions": []
        }
        
        # Extract ranges from constraints
        constraints_text = sections.get('constraints', '')
        if constraints_text:
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
        
        # Generate code templates
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
        
        # Calculate confidence score
        confidence = 0.5  # Base confidence
        if sections.get('title'): confidence += 0.1
        if sections.get('description') and len(sections['description']) > 50: confidence += 0.2
        if examples["sampleCases"]: confidence += 0.2
        if sections.get('constraints'): confidence += 0.1
        
        confidence = min(confidence, 1.0)
        
        # Build final problem object
        problem = {
            "basicInfo": {
                "questionId": problem_id,
                "title": sections.get('title', f"Problem {problem_id}"),
                "description": sections.get('description', ''),
                "difficulty": difficulty,
                "category": category,
                "tags": tags,
                "source": str(file_path)
            },
            "constraints": constraints,
            "examples": examples,
            "codeTemplates": templates,
            "metadata": {
                "extractedFrom": str(file_path),
                "confidence": confidence,
                "notes": f"Extracted from Project CodeNet problem {problem_id}"
            }
        }
        
        return problem
        
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return None

def main():
    """Main function to extract all problems with improved handling"""
    base_dir = Path(__file__).parent
    problems_dir = base_dir / "doc" / "problem_descriptions"
    
    if not problems_dir.exists():
        print(f"Problem descriptions directory not found: {problems_dir}")
        return
    
    print(f"Extracting problems from: {problems_dir}")
    
    html_files = list(problems_dir.glob("p*.html"))
    print(f"Found {len(html_files)} problem files")
    
    problems = []
    processed = 0
    skipped = 0
    
    for html_file in sorted(html_files):
        if processed % 100 == 0:
            print(f"Processed {processed}/{len(html_files)} problems... (skipped: {skipped})")
        
        problem = extract_problem_improved(html_file)
        if problem:
            problems.append(problem)
        else:
            skipped += 1
        
        processed += 1
    
    print(f"Successfully extracted {len(problems)} problems (skipped {skipped})")
    
    # Create output JSON
    output = {"problems": problems}
    
    # Write to file
    output_file = base_dir / "extracted_problems_complete.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"Saved all problems to: {output_file}")
    print(f"Total problems extracted: {len(problems)}")
    
    # Print summary statistics
    difficulties = {}
    categories = {}
    confidence_levels = {'high': 0, 'medium': 0, 'low': 0}
    
    for problem in problems:
        diff = problem["basicInfo"]["difficulty"]
        cat = problem["basicInfo"]["category"]
        conf = problem["metadata"]["confidence"]
        
        difficulties[diff] = difficulties.get(diff, 0) + 1
        categories[cat] = categories.get(cat, 0) + 1
        
        if conf >= 0.8:
            confidence_levels['high'] += 1
        elif conf >= 0.6:
            confidence_levels['medium'] += 1
        else:
            confidence_levels['low'] += 1
    
    print("\nDifficulty distribution:")
    for diff, count in sorted(difficulties.items()):
        print(f"  {diff}: {count}")
    
    print("\nCategory distribution:")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")
    
    print("\nConfidence distribution:")
    for level, count in confidence_levels.items():
        print(f"  {level}: {count}")

if __name__ == "__main__":
    main()
