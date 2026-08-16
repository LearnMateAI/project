"""
Create structurally realistic synthetic Sri Lankan legal PDFs for pipeline smoke tests.

These are NOT real statutes — they mimic Cap./Chapter/Section layout so Stage 1
structure detection and semantic chunking can be proven before any real corpus exists.
"""
from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "sample_pdfs"


DOCUMENTS: dict[str, list[tuple[str, str]]] = {
    "sample_penal_code_excerpt.pdf": [
        ("title", "PENAL CODE (SYNTHETIC EXCERPT) — Cap. 25"),
        ("header", "Official Reprint (Synthetic) | Page {page}"),
        ("chapter", "CHAPTER XVII — OF OFFENCES AGAINST PROPERTY"),
        (
            "section",
            "366. Whoever, intending to take dishonestly any movable property out of the "
            "possession of any person without that person's consent, moves that property "
            "in order to such taking, is said to commit theft.",
        ),
        (
            "section",
            "367. Whoever commits theft shall be punished with imprisonment of either "
            "description for a term which may extend to three years, or with fine, or with both.",
        ),
        (
            "section",
            "379. In all robbery there is either theft or extortion. Theft is robbery if, "
            "in order to the committing of the theft, or in committing the theft, or in "
            "carrying away or attempting to carry away property obtained by the theft, "
            "the offender, for that end, voluntarily causes or attempts to cause to any "
            "person death or hurt or wrongful restraint, or fear of instant death or of "
            "instant hurt or of instant wrongful restraint.",
        ),
        (
            "section",
            "380. Whoever commits robbery shall be punished with rigorous imprisonment "
            "for a term which may extend to ten years, and shall also be liable to fine.",
        ),
        ("chapter", "CHAPTER XVIII — OF OFFENCES RELATING TO DOCUMENTS"),
        (
            "section",
            "452. A person is said to make a false document who dishonestly or fraudulently "
            "makes, signs, seals or executes a document or part of a document, or makes any "
            "mark denoting the execution of a document, with the intention of causing it to "
            "be believed that such document or part of a document was made, signed, sealed "
            "or executed by or by the authority of a person by whom or by whose authority "
            "he knows that it was not made, signed, sealed or executed.",
        ),
    ],
    "sample_constitution_fr.pdf": [
        ("title", "CONSTITUTION OF SRI LANKA (SYNTHETIC) — CHAPTER III"),
        ("header", "Constitution (Synthetic) | Page {page}"),
        ("chapter", "CHAPTER III — FUNDAMENTAL RIGHTS"),
        (
            "section",
            "10. Every person is entitled to freedom of thought, conscience and religion, "
            "including the freedom to have or to adopt a religion or belief of his choice.",
        ),
        (
            "section",
            "11. No person shall be subjected to torture or to cruel, inhuman or degrading "
            "treatment or punishment.",
        ),
        (
            "section",
            "12. (1) All persons are equal before the law and are entitled to the equal "
            "protection of the law. (2) No citizen shall be discriminated against on the "
            "grounds of race, religion, language, caste, sex, political opinion, place of "
            "birth or any one of such grounds.",
        ),
        (
            "section",
            "13. (1) No person shall be arrested except according to procedure established "
            "by law. Any person arrested shall be informed of the reason for his arrest. "
            "(2) Every person held in custody shall be brought before the judge of the "
            "nearest competent court according to procedure established by law.",
        ),
        (
            "section",
            "14. Every citizen is entitled to the freedom of speech and expression including "
            "publication; the freedom of peaceful assembly; the freedom of association; "
            "and the freedom to engage by himself or in association with others in any "
            "lawful occupation, profession, trade, business or enterprise.",
        ),
    ],
    "sample_evidence_ordinance.pdf": [
        ("title", "EVIDENCE ORDINANCE (SYNTHETIC EXCERPT)"),
        ("header", "Evidence Ordinance (Synthetic) | Page {page}"),
        ("part", "PART I — RELEVANCY OF FACTS"),
        (
            "section",
            "5. Evidence may be given in any suit or proceeding of the existence or "
            "non-existence of every fact in issue and of such other facts as are "
            "hereinafter declared to be relevant, and of no others.",
        ),
        (
            "section",
            "6. Facts which, though not in issue, are so connected with a fact in issue "
            "as to form part of the same transaction, are relevant, whether they occurred "
            "at the same time and place or at different times and places.",
        ),
        ("part", "PART II — ON PROOF"),
        (
            "section",
            "59. All facts, except the contents of documents, may be proved by oral evidence.",
        ),
        (
            "section",
            "60. Oral evidence must, in all cases whatever, be direct; that is to say— "
            "if it refers to a fact which could be seen, it must be the evidence of a "
            "witness who says he saw it; if it refers to a fact which could be heard, "
            "it must be the evidence of a witness who says he heard it.",
        ),
        (
            "section",
            "91. When the terms of a contract, or of a grant, or of any other disposition "
            "of property, have been reduced to the form of a document, and in all cases "
            "in which any matter is required by law to be reduced to the form of a "
            "document, no evidence shall be given in proof of the terms of such contract, "
            "grant or other disposition of property, or of such matter, except the "
            "document itself, or secondary evidence of its contents in cases in which "
            "secondary evidence is admissible.",
        ),
    ],
    "sample_civil_procedure.pdf": [
        ("title", "CIVIL PROCEDURE CODE (SYNTHETIC EXCERPT) — Cap. 105"),
        ("header", "Civil Procedure Code (Synthetic) | Page {page}"),
        ("chapter", "CHAPTER I — PRELIMINARY"),
        (
            "section",
            "1. This Ordinance may be cited as the Civil Procedure Code.",
        ),
        (
            "section",
            "5. Every application to a court for relief or remedy obtainable through "
            "the exercise of the court's power or authority, or otherwise to invite "
            "its interference, constitutes an action.",
        ),
        ("chapter", "CHAPTER II — OF THE MODE OF INSTITUTION OF ACTION"),
        (
            "section",
            "40. Every action shall ordinarily be instituted by presenting a written "
            "plaint to the court of first instance of competent jurisdiction.",
        ),
        (
            "section",
            "46. The plaint shall contain a statement in a summary form of the material "
            "facts on which the plaintiff relies for his claim, but not the evidence by "
            "which they are to be proved, and shall be divided into paragraphs numbered "
            "consecutively.",
        ),
        (
            "section",
            "75. The defendant may present a written answer. The answer shall contain "
            "a statement of the material facts on which the defendant relies for his "
            "defence, and shall specifically deny or admit each of the allegations of "
            "fact in the plaint.",
        ),
    ],
    "sample_companies_act.pdf": [
        ("title", "COMPANIES ACT (SYNTHETIC EXCERPT)"),
        ("header", "Companies Act (Synthetic) | Page {page}"),
        ("part", "PART I — INCORPORATION OF COMPANIES"),
        (
            "section",
            "2. Any two or more persons associated for any lawful purpose may, by "
            "subscribing their names to a memorandum of association and otherwise "
            "complying with the requirements of this Act in respect of registration, "
            "form an incorporated company.",
        ),
        (
            "section",
            "3. The memorandum of every company shall state the name of the company, "
            "whether the company is limited by shares or by guarantee, and the objects "
            "for which the company is established.",
        ),
        ("part", "PART II — DIRECTORS AND MANAGEMENT"),
        (
            "section",
            "45. Every company shall have at least one director. A director shall act "
            "in good faith and in the best interests of the company, and shall exercise "
            "the degree of care, diligence and skill that a reasonably prudent person "
            "would exercise in comparable circumstances.",
        ),
        (
            "section",
            "52. A director who is interested in a transaction or proposed transaction "
            "with the company shall disclose the nature and extent of that interest to "
            "the board as soon as practicable after the director becomes aware of the "
            "facts that give rise to the interest.",
        ),
    ],
    "sample_sc_judgment.pdf": [
        ("title", "IN THE SUPREME COURT OF SRI LANKA (SYNTHETIC JUDGMENT)"),
        ("header", "S.C. Appeal No. 99/2020 (Synthetic) | Page {page}"),
        ("chapter", "JUDGMENT"),
        (
            "section",
            "1. This appeal raises a question of law as to whether parol evidence may "
            "be led to establish a constructive trust notwithstanding section 2 of the "
            "Prevention of Frauds Ordinance and sections 91 and 92 of the Evidence Ordinance.",
        ),
        (
            "section",
            "2. The appellant contends that the notarially executed transfer was intended "
            "only as security, and that the true intention of the parties gives rise to "
            "a constructive trust under Chapter IX of the Trusts Ordinance.",
        ),
        (
            "section",
            "3. Held: The Prevention of Frauds Ordinance, designed to prevent fraud, "
            "cannot be permitted to be used as an instrument of fraud. In appropriate "
            "cases of constructive trust, informal writings and parol evidence may be "
            "received to prove the true nature of the transaction.",
        ),
        (
            "section",
            "4. Ratio: Where a party seeks to establish a constructive trust arising "
            "from the true intention of the parties, sections 91 and 92 of the Evidence "
            "Ordinance do not bar evidence led to invalidate or explain the instrument "
            "on grounds recognised by the provisos thereto, including fraud.",
        ),
    ],
}


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "DocTitle",
            parent=base["Heading1"],
            fontSize=14,
            spaceAfter=18,
            alignment=1,
        ),
        "header": ParagraphStyle(
            "RunningHeader",
            parent=base["Normal"],
            fontSize=8,
            textColor="grey",
            spaceAfter=12,
        ),
        "chapter": ParagraphStyle(
            "ChapterHead",
            parent=base["Heading2"],
            fontSize=12,
            spaceBefore=16,
            spaceAfter=10,
        ),
        "part": ParagraphStyle(
            "PartHead",
            parent=base["Heading2"],
            fontSize=12,
            spaceBefore=16,
            spaceAfter=10,
        ),
        "section": ParagraphStyle(
            "SectionBody",
            parent=base["Normal"],
            fontSize=10,
            leading=14,
            spaceAfter=10,
        ),
    }


def build_pdf(filename: str, blocks: list[tuple[str, str]]) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / filename
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=0.9 * inch,
        rightMargin=0.9 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    styles = _styles()
    story = []
    page_no = 1
    for kind, text in blocks:
        if kind == "header":
            story.append(Paragraph(text.format(page=page_no), styles["header"]))
            page_no += 1
        else:
            story.append(Paragraph(text, styles[kind]))
            if kind in {"chapter", "part"}:
                story.append(Spacer(1, 4))
    # Force a second page with a page-number-only footer line to test stripping
    story.append(Spacer(1, 200))
    story.append(Paragraph(f"Page {page_no}", styles["header"]))
    story.append(Paragraph("Printed by the Synthetic Government Press", styles["header"]))
    doc.build(story)
    return path


def main() -> int:
    written = []
    for name, blocks in DOCUMENTS.items():
        path = build_pdf(name, blocks)
        written.append(path)
        print(f"wrote {path}")
    print(f"created {len(written)} sample PDFs in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
