#!/usr/bin/env python3
"""
Extract GQL Examples from Documentation

Scans documentation for GQL code blocks and extracts them as testable examples.

CANARY: REQ=REQ-EXTRACT-GQL-001; FEATURE="GQLExtraction"; ASPECT=Tooling; STATUS=TESTED

Usage:
    python extract_gql_examples.py --docs-path /path/to/docs --output-dir ./extracted
"""
import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List


@dataclass
class GQLExample:
    """Represents an extracted GQL example."""
    source_file: str
    line_number: int
    description: str
    gql_code: str
    is_complete: bool  # Has full query vs snippet


# Pattern for GQL code blocks
GQL_BLOCK_PATTERN = re.compile(
    r'```(?:gql|cypher|graphql)\s*\n(.*?)```',
    re.DOTALL | re.IGNORECASE
)

# Pattern for inline GQL (single backticks)
INLINE_GQL_PATTERN = re.compile(
    r'`((?:MATCH|CREATE|RETURN|DELETE|MERGE|SET|REMOVE|WITH|CALL|BEGIN|COMMIT|ROLLBACK)[^`]+)`',
    re.IGNORECASE
)


def is_complete_query(gql: str) -> bool:
    """Check if GQL is a complete query vs a snippet."""
    gql_upper = gql.upper()

    # Must have a return or be a mutation
    has_output = any(kw in gql_upper for kw in ["RETURN", "CREATE", "DELETE", "MERGE", "SET"])

    # Should not be a fragment (no ellipsis, etc.)
    is_fragment = "..." in gql or gql.strip().endswith(",")

    return has_output and not is_fragment


def extract_description(lines: List[str], block_start: int) -> str:
    """Extract description from lines preceding a code block."""
    description_lines = []

    # Look back up to 5 lines for description
    for i in range(block_start - 1, max(0, block_start - 6), -1):
        line = lines[i].strip()

        # Stop at empty line or another code block
        if not line or line.startswith("```"):
            break

        # Skip list markers but keep content
        if line.startswith(("-", "*", "#")):
            line = line.lstrip("-*# ")

        description_lines.insert(0, line)

    return " ".join(description_lines)[:200]  # Limit length


def extract_from_file(file_path: Path, base_path: Path) -> List[GQLExample]:
    """Extract GQL examples from a single file."""
    examples = []

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)
        return examples

    lines = content.split("\n")
    relative_path = str(file_path.relative_to(base_path))

    # Find code blocks
    for match in GQL_BLOCK_PATTERN.finditer(content):
        gql_code = match.group(1).strip()

        # Find line number
        line_number = content[:match.start()].count("\n") + 1

        # Get description
        description = extract_description(lines, line_number - 1)

        example = GQLExample(
            source_file=relative_path,
            line_number=line_number,
            description=description,
            gql_code=gql_code,
            is_complete=is_complete_query(gql_code)
        )
        examples.append(example)

    return examples


def extract_all_gql(docs_path: Path) -> List[GQLExample]:
    """Extract GQL examples from all documentation files."""
    all_examples = []

    for pattern in ["**/*.md", "**/*.rst", "**/*.txt"]:
        for file_path in docs_path.glob(pattern):
            # Skip hidden and vendor directories
            if any(part.startswith(".") or part in ["node_modules", "vendor"]
                   for part in file_path.parts):
                continue

            examples = extract_from_file(file_path, docs_path)
            all_examples.extend(examples)

    return all_examples


def save_examples(examples: List[GQLExample], output_dir: Path):
    """Save extracted examples as individual .gql files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Group by source file
    by_source = {}
    for example in examples:
        source = Path(example.source_file).stem
        if source not in by_source:
            by_source[source] = []
        by_source[source].append(example)

    total_saved = 0

    for source, source_examples in by_source.items():
        # Only save complete queries
        complete = [e for e in source_examples if e.is_complete]

        for i, example in enumerate(complete, 1):
            filename = f"{source}_{i:03d}.gql"
            filepath = output_dir / filename

            # Create header comment
            header = f"""-- Extracted from: {example.source_file}:{example.line_number}
-- Description: {example.description or 'No description'}
-- Generated: {datetime.now(timezone.utc).isoformat()}

"""
            with open(filepath, "w") as f:
                f.write(header)
                f.write(example.gql_code)
                f.write("\n")

            total_saved += 1

    return total_saved


def main():
    parser = argparse.ArgumentParser(description="Extract GQL examples from documentation")
    parser.add_argument("--docs-path", "-d", type=Path, required=True,
                        help="Path to documentation directory")
    parser.add_argument("--output-dir", "-o", type=Path, default=Path("extracted_gql"),
                        help="Output directory for extracted examples")
    parser.add_argument("--list-only", action="store_true",
                        help="Only list examples, don't save files")
    parser.add_argument("--include-snippets", action="store_true",
                        help="Include incomplete code snippets")

    args = parser.parse_args()

    if not args.docs_path.exists():
        print(f"Error: Documentation path does not exist: {args.docs_path}", file=sys.stderr)
        sys.exit(1)

    # Extract examples
    print(f"Scanning {args.docs_path} for GQL examples...")
    examples = extract_all_gql(args.docs_path)

    # Filter by completeness
    if not args.include_snippets:
        complete = [e for e in examples if e.is_complete]
        print(f"Found {len(examples)} GQL blocks, {len(complete)} are complete queries")
        examples = complete
    else:
        print(f"Found {len(examples)} GQL blocks")

    if args.list_only:
        # Just list the examples
        for example in examples:
            status = "COMPLETE" if example.is_complete else "SNIPPET"
            print(f"\n[{status}] {example.source_file}:{example.line_number}")
            print(f"  Description: {example.description[:80]}...")
            print(f"  Code preview: {example.gql_code[:60]}...")
    else:
        # Save to files
        saved = save_examples(examples, args.output_dir)
        print(f"\nSaved {saved} GQL examples to {args.output_dir}/")

    # Summary
    by_source = {}
    for example in examples:
        source = example.source_file
        by_source[source] = by_source.get(source, 0) + 1

    print("\nExamples by source file:")
    for source, count in sorted(by_source.items(), key=lambda x: -x[1])[:10]:
        print(f"  {source}: {count}")


if __name__ == "__main__":
    main()
