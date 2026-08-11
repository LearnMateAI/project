"""
Turning cleaned pages into the chunks that get embedded.

Chunking is sub-page, deliberately. One vector per page averages every provision on that
page together, so the specific article a question asks about is diluted by everything
printed beside it -- and a keyword-dense contents page out-scores the article text,
because a list of chapter titles matches almost any topical query.

    cleaned pages  ->  split  ->  filter  ->  Documents carrying their page number
"""

from typing import Dict, List

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .. import config
from .clean import is_substantive, looks_like_contents

# Ordered so a split falls at the largest boundary that fits: sentence ends first, then
# the numbered-clause markers that structure legal and academic prose -- "(2)", "(iii)" --
# then clause punctuation, and only then whitespace.
_SEPARATORS = [
    ". ",   # sentence end
    "; ",   # clause end, very common in legal prose
    ": ",
    "? ",
    "! ",
    ") ",   # tail of a numbered clause marker
    ", ",
    " ",
    "",
]


def build_splitter(chunk_size: int = None, chunk_overlap: int = None
                   ) -> RecursiveCharacterTextSplitter:
    """
    The text splitter used for every document.

    The overlap keeps a provision that straddles a chunk boundary retrievable from either
    side, which matters most for exactly the long sentences legal text is made of.
    """
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size or config.CHUNK_SIZE,
        chunk_overlap=chunk_overlap or config.CHUNK_OVERLAP,
        separators=_SEPARATORS,
        keep_separator=True,
        length_function=len,
    )


def pages_to_documents(pages: List[Dict], doc_id, filename: str,
                       splitter: RecursiveCharacterTextSplitter = None) -> List[Document]:
    """
    Split cleaned pages into LangChain Documents carrying their provenance.

    `chunk_index` is per page and, with doc_id and page_number, gives every chunk a stable
    identity -- that triple is the unique key the vector store upserts on, so re-ingesting
    a document overwrites its chunks instead of duplicating them.

    The page number riding in the metadata is what lets the chat agent cite "p.52" and
    what `build_source_text` uses to read whole pages back.
    """
    splitter = splitter or build_splitter()

    documents = []
    for page in pages:
        content = page.get("page_content", "")
        if not content:
            continue

        index = 0
        # Checked here rather than per chunk: the splitter treats ". " as a boundary, so
        # by the time a contents page has been split its dot leaders have been broken
        # apart and the chunks no longer look like what they are. The page still does.
        if looks_like_contents(content, min_leaders=4):
            continue

        for piece in splitter.split_text(content):
            piece = piece.strip()
            # Two cheap filters, in order of cost: too short to carry meaning (a running
            # head, a stray caption), then contents-page shapes the page check missed.
            if not is_substantive(piece, config.MIN_CHUNK_CHARS):
                continue
            if looks_like_contents(piece):
                continue

            documents.append(Document(
                page_content=piece,
                metadata={
                    "doc_id": doc_id,
                    "filename": filename,
                    "page_number": page["page_number"],
                    "chunk_index": index,
                    "source": filename,
                },
            ))
            index += 1
    return documents
