import re
from typing import List, Union
import tiktoken
from llama_index.core.node_parser import MarkdownNodeParser, TokenTextSplitter
from llama_index.core.schema import BaseNode, Document, TextNode


def chunk_md(
    md_string: str,
    chunk_size: int = 512,
    overlap: Union[int, float, None] = None,
    overlap_pct: float = 0.10,
    tokenizer_model: str = "gpt-4o",
) -> List[BaseNode]:
    """
    Chunks a Markdown document based on its headers.
    If a header section exceeds `chunk_size` (max tokens), it splits that section
    using token-based chunking with the specified overlap.
    
    Extracts embedded page markers (e.g. 'START OF PAGE_NUMBER: {n}' or '<!-- PAGE {n} START -->')
    and attaches page number metadata to each chunk. If a chunk spans or overlaps across
    page boundaries, its metadata records all relevant page numbers.
    
    Args:
        md_string: The Markdown string containing optional embedded page markers.
        chunk_size: Maximum token count per chunk (default: 512).
        overlap: Token overlap as an int or float percentage. If None, uses `overlap_pct`.
        overlap_pct: Default overlap percentage if `overlap` is not explicitly set (default: 0.10).
        tokenizer_model: Tiktoken model name for token counting (default: 'gpt-4o').
        
    Returns:
        A list of LlamaIndex BaseNode (TextNode) objects, each containing:
            - text: Clean Markdown chunk content.
            - metadata: {'page_number': int | list[int], 'page_number': list[int], 'header_path': str, ...}
    """
    # 1. Determine token overlap
    if isinstance(overlap, int):
        chunk_overlap = overlap
    elif isinstance(overlap, float):
        chunk_overlap = max(1, int(chunk_size * overlap))
    else:
        chunk_overlap = max(1, int(chunk_size * overlap_pct))

    # 2. Setup tokenizer
    try:
        enc = tiktoken.encoding_for_model(tokenizer_model)
    except Exception:
        enc = tiktoken.get_encoding("cl100k_base")
    tokenizer_fn = enc.encode

    # 3. Detect and extract page ranges (supports both 'START OF PAGE_NUMBER: X' and '<!-- PAGE X START -->')
    page_pattern = (
        r"(?:START OF PAGE_NUMBER:\s*(\d+)|<!--\s*PAGE\s*(\d+)\s*START\s*-->)\s*\n?"
        r"(.*?)"
        r"(?:\n?\s*(?:END OF PAGE_NUMBER:\s*(?:\1|\2)|<!--\s*PAGE\s*(?:\1|\2)\s*END\s*-->)|\Z)"
    )

    matches = list(re.finditer(page_pattern, md_string, re.DOTALL | re.IGNORECASE))
    page_spans = []

    if matches:
        clean_parts = []
        curr_pos = 0
        for m in matches:
            p_num = int(m.group(1) or m.group(2))
            content = m.group(3).strip()
            start = curr_pos
            end = start + len(content)
            page_spans.append((p_num, start, end))
            clean_parts.append(content)
            curr_pos = end + 2  # account for '\n\n' separator
        clean_md = "\n\n".join(clean_parts)
    else:
        clean_md = md_string.strip()
        page_spans.append((1, 0, len(clean_md)))

    def get_pages_for_range(start_idx: int, end_idx: int) -> list[int]:
        pages = []
        for p_num, p_start, p_end in page_spans:
            # Overlap check between [start_idx, end_idx] and [p_start, p_end]
            if max(start_idx, p_start) < min(end_idx, p_end):
                pages.append(p_num)
        return pages if pages else [1]

    # 4. Parse document by Markdown headers
    md_parser = MarkdownNodeParser()
    initial_nodes = md_parser.get_nodes_from_documents([Document(text=clean_md)])

    # 5. Token splitter for oversized sections
    token_splitter = TokenTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        tokenizer=tokenizer_fn,
    )

    final_nodes: List[BaseNode] = []
    doc_cursor = 0

    for node in initial_nodes:
        node_text = node.text.strip()
        if not node_text:
            continue

        # Locate section position in clean_md
        node_loc = clean_md.find(node.text, doc_cursor)
        if node_loc != -1:
            doc_cursor = node_loc
        else:
            node_loc = clean_md.find(node.text)

        token_count = len(tokenizer_fn(node.text))

        if token_count <= chunk_size:
            # Section fits inside token budget
            pages = get_pages_for_range(node_loc, node_loc + len(node.text))
            meta = dict(node.metadata)
            meta["page_number"] = pages
            meta["token_count"] = token_count
            final_nodes.append(TextNode(text=node_text, metadata=meta))
        else:
            # Section exceeds budget -> Split by tokens with overlap
            sub_texts = token_splitter.split_text(node.text)
            sub_cursor = 0
            for sub_text in sub_texts:
                clean_sub = sub_text.strip()
                if not clean_sub:
                    continue

                sub_loc = node.text.find(sub_text, sub_cursor)
                if sub_loc != -1:
                    sub_cursor = sub_loc + 1
                    g_start = node_loc + sub_loc
                    g_end = g_start + len(sub_text)
                else:
                    g_start = node_loc
                    g_end = node_loc + len(node.text)

                pages = get_pages_for_range(g_start, g_end)
                meta = dict(node.metadata)
                meta["page_number"] = pages
                meta["token_count"] = len(tokenizer_fn(clean_sub))
                final_nodes.append(TextNode(text=clean_sub, metadata=meta))

    return final_nodes

def get_documents(nodes: List[BaseNode], book_id: str, grade) -> list[dict]:
    doc_list = []
    for node in nodes:
        page_val = node.metadata.get("page_number")
        header_val = node.metadata.get("header_path")
        token_val = node.metadata.get("token_count")
        doc_list.append(
            {
                "book_id": book_id,
                "page_number": page_val,
                "header_path": header_val,
                "token_count": token_val,
                "text": node.text,
                "grade": grade
            }
        )
    return doc_list

# Alias for backward compatibility / explicit naming
get_smart_markdown_chunks = chunk_md


if __name__ == "__main__":
    sample_text = """START OF PAGE_NUMBER: 1
# Chapter 1: Introduction
Artificial intelligence is transforming every aspect of technology.
It begins with basic algorithms and spans all the way to deep learning.
END OF PAGE_NUMBER: 1

START OF PAGE_NUMBER: 2
Here is continuation text under Chapter 1 on page 2.
## 1.1 Neural Networks
Neural networks mimic biological neurons to process complex data.
END OF PAGE_NUMBER: 2
"""
    nodes = chunk_md(sample_text, chunk_size=1000, overlap_pct=0.10)
    print(f"Total chunks created: {len(nodes)}")
    for i, n in enumerate(nodes):
        print(f"\n--- Chunk {i} ---")
        print(f"Pages: {n.metadata.get('page_number')} (all: {n.metadata.get('page_number')})")
        print(f"Header: {n.metadata.get('header_path')}")
        print(f"Tokens: {n.metadata.get('token_count')}")
        print(f"Content:\n{n.text}")