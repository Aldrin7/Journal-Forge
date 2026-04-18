"""
PaperForge — OMML to LaTeX Converter
Pure-Python Office Math Markup Language → LaTeX transformation.
No external dependencies needed.
"""
import re
import xml.etree.ElementTree as ET
from typing import Optional, List, Dict, Any


# OMML namespace
NS = {
    'm': 'http://schemas.openxmlformats.org/officeDocument/2006/math',
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
}

# Common OMML element → LaTeX mappings
FUNCTION_NAMES = {
    'sin', 'cos', 'tan', 'cot', 'sec', 'csc',
    'arcsin', 'arccos', 'arctan', 'arccot',
    'sinh', 'cosh', 'tanh', 'coth',
    'log', 'ln', 'lg', 'exp',
    'lim', 'limsup', 'liminf',
    'max', 'min', 'sup', 'inf',
    'det', 'dim', 'ker', 'deg', 'gcd',
    'arg', 'hom', 'Pr',
}

ACCENT_MAP = {
    '̂': r'\hat',
    '̃': r'\tilde',
    '̄': r'\bar',
    '⃗': r'\vec',
    '̇': r'\dot',
    '̈': r'\ddot',
    '̆': r'\breve',
    '̊': r'\mathring',
}

DELIMITER_MAP = {
    '(': '(',
    ')': ')',
    '[': r'\lbrack',
    ']': r'\rbrack',
    '{': r'\lbrace',
    '}': r'\rbrace',
    '|': '|',
    '‖': r'\|',
    '⟨': r'\langle',
    '⟩': r'\rangle',
    '/': '/',
    '\\': r'\backslash',
}

# Vertical justification mapping
VERT_JUST = {
    'top': 't',
    'bot': 'b',
    'center': '',
}


def omml_to_latex(omml_element) -> str:
    """
    Convert an OMML XML element to a LaTeX string.
    Handles: fractions, superscripts, subscripts, radicals, 
    integrals, summations, matrices, brackets, accents, 
    n-ary operators, functions, and plain text.
    """
    if omml_element is None:
        return ""

    # If it's raw XML string, parse it
    if isinstance(omml_element, str):
        try:
            root = ET.fromstring(omml_element)
            return _convert_element(root)
        except ET.ParseError:
            return omml_element

    return _convert_element(omml_element)


def _convert_element(el) -> str:
    """Recursively convert an OMML element to LaTeX."""
    tag = _localname(el)

    handlers = {
        'oMath': _convert_omath,
        'oMathPara': _convert_omath_para,
        'oMathParaPr': _skip,
        'r': _convert_run,
        'rPr': _skip,
        't': _convert_text,
        'f': _convert_fraction,
        'fPr': _skip,
        'num': _convert_container,
        'den': _convert_container,
        'sup': _convert_container,
        'sub': _convert_container,
        'sSup': _convert_superscript,
        'sSub': _convert_subscript,
        'sSubSup': _convert_sub_sup,
        'rad': _convert_radical,
        'deg': _convert_container,
        'e': _convert_container,
        'nary': _convert_nary,
        'naryPr': _skip,
        'lim': _convert_container,
        'limLow': _convert_limit_lower,
        'limUpp': _convert_limit_upper,
        'func': _convert_function,
        'funcPr': _skip,
        'fname': _convert_container,
        'd': _convert_delimiter,
        'dPr': _skip,
        'eqArr': _convert_equation_array,
        'm': _convert_matrix,
        'mPr': _skip,
        'mr': _convert_matrix_row,
        'box': _convert_container,
        'borderBox': _convert_border_box,
        'bar': _convert_bar,
        'barPr': _skip,
        'acc': _convert_accent,
        'accPr': _skip,
        'chr': _skip,
        'begChr': _skip,
        'endChr': _skip,
        'sepChr': _skip,
        'grow': _skip,
        'ctrlPr': _skip,
        'argSz': _skip,
        'groupChr': _convert_group_char,
        'groupChrPr': _skip,
    }

    handler = handlers.get(tag, _convert_default)
    return handler(el)


def _localname(el) -> str:
    """Get local name without namespace."""
    if '}' in el.tag:
        return el.tag.split('}', 1)[1]
    return el.tag


def _skip(el) -> str:
    """Skip property elements."""
    return ""


def _convert_omath(el) -> str:
    """Convert <m:oMath> root element."""
    parts = []
    for child in el:
        parts.append(_convert_element(child))
    return ''.join(parts)


def _convert_omath_para(el) -> str:
    """Convert <m:oMathPara> — a display equation."""
    parts = []
    for child in el:
        if _localname(child) == 'oMath':
            parts.append(_convert_element(child))
    return ' '.join(parts)


def _convert_container(el) -> str:
    """Convert a container element (num, den, sup, sub, e, deg, lim, fname)."""
    parts = []
    for child in el:
        parts.append(_convert_element(child))
    return ''.join(parts)


def _convert_run(el) -> str:
    """Convert <m:r> — a text run with optional formatting."""
    text_parts = []
    is_bold = False
    is_italic = False
    is_script = None  # 'sup' or 'sub'

    # Check run properties
    for child in el:
        tag = _localname(child)
        if tag == 'rPr':
            for prop in child:
                ptag = _localname(prop)
                if ptag == 'b':
                    is_bold = True
                elif ptag == 'i':
                    is_italic = True
                elif ptag == 'scr':
                    font = prop.get(f'{{{NS["m"]}}}val', prop.get('val', ''))
                    # Map script fonts
                elif ptag == 'sty':
                    style = prop.get(f'{{{NS["m"]}}}val', prop.get('val', ''))
        elif tag == 't':
            text_parts.append(child.text or '')

    text = ''.join(text_parts)

    if not text:
        return ""

    # Wrap in formatting
    if is_bold:
        text = r'\mathbf{' + text + '}'
    if is_italic:
        text = r'\mathit{' + text + '}'

    return text


def _convert_text(el) -> str:
    """Convert <m:t> text node."""
    return el.text or ""


def _convert_fraction(el) -> str:
    """Convert <m:f> — fraction."""
    num = ""
    den = ""

    for child in el:
        tag = _localname(child)
        if tag == 'num':
            num = _convert_container(child)
        elif tag == 'den':
            den = _convert_container(child)

    # Check for fraction type
    fpr = el.find('m:fPr', NS)
    if fpr is not None:
        for prop in fpr:
            if _localname(prop) == 'type':
                ftype = prop.get(f'{{{NS["m"]}}}val', prop.get('val', 'bar'))
                if ftype == 'noBar':
                    return r'\genfrac{}{}{0pt}{}{' + num + '}{' + den + '}'
                elif ftype == 'skw':
                    return r'\sfrac{' + num + '}{' + den + '}'

    return r'\frac{' + num + '}{' + den + '}'


def _convert_superscript(el) -> str:
    """Convert <m:sSup> — superscript."""
    base = ""
    sup = ""

    for child in el:
        tag = _localname(child)
        if tag == 'e':
            base = _convert_container(child)
        elif tag == 'sup':
            sup = _convert_container(child)

    if not base:
        base = "{}"
    return base + '^{' + sup + '}'


def _convert_subscript(el) -> str:
    """Convert <m:sSub> — subscript."""
    base = ""
    sub = ""

    for child in el:
        tag = _localname(child)
        if tag == 'e':
            base = _convert_container(child)
        elif tag == 'sub':
            sub = _convert_container(child)

    if not base:
        base = "{}"
    return base + '_{' + sub + '}'


def _convert_sub_sup(el) -> str:
    """Convert <m:sSubSup> — subscript and superscript."""
    base = ""
    sub = ""
    sup = ""

    for child in el:
        tag = _localname(child)
        if tag == 'e':
            base = _convert_container(child)
        elif tag == 'sub':
            sub = _convert_container(child)
        elif tag == 'sup':
            sup = _convert_container(child)

    if not base:
        base = "{}"
    return base + '_{' + sub + '}^{' + sup + '}'


def _convert_radical(el) -> str:
    """Convert <m:rad> — radical (square root, nth root)."""
    deg = ""
    expr = ""

    for child in el:
        tag = _localname(child)
        if tag == 'deg':
            deg = _convert_container(child)
        elif tag == 'e':
            expr = _convert_container(child)

    if deg:
        return r'\sqrt[' + deg + ']{' + expr + '}'
    return r'\sqrt{' + expr + '}'


def _convert_nary(el) -> str:
    """Convert <m:nary> — n-ary operator (sum, product, integral)."""
    chr_val = ""
    sub = ""
    sup = ""
    expr = ""

    for child in el:
        tag = _localname(child)
        if tag == 'naryPr':
            for prop in child:
                if _localname(prop) == 'chr':
                    chr_val = prop.get(f'{{{NS["m"]}}}val', prop.get('val', ''))
        elif tag == 'sub':
            sub = _convert_container(child)
        elif tag == 'sup':
            sup = _convert_container(child)
        elif tag == 'e':
            expr = _convert_container(child)

    # Map n-ary characters to LaTeX
    nary_map = {
        '∑': r'\sum',
        '∏': r'\prod',
        '∐': r'\coprod',
        '∫': r'\int',
        '∬': r'\iint',
        '∭': r'\iiint',
        '∮': r'\oint',
        '⋃': r'\bigcup',
        '⋂': r'\bigcap',
        '⨀': r'\bigodot',
        '⨁': r'\bigoplus',
        '⨂': r'\bigotimes',
        '⋁': r'\bigvee',
        '⋀': r'\bigwedge',
    }

    op = nary_map.get(chr_val, chr_val or r'\sum')

    result = op
    if sub:
        result += '_{' + sub + '}'
    if sup:
        result += '^{' + sup + '}'
    if expr:
        result += ' ' + expr

    return result


def _convert_limit_lower(el) -> str:
    """Convert <m:limLow> — lower limit (lim_{x→0})."""
    base = ""
    lim = ""

    for child in el:
        tag = _localname(child)
        if tag == 'e':
            base = _convert_container(child)
        elif tag == 'lim':
            lim = _convert_container(child)

    return base + '_{' + lim + '}'


def _convert_limit_upper(el) -> str:
    """Convert <m:limUpp> — upper limit."""
    base = ""
    lim = ""

    for child in el:
        tag = _localname(child)
        if tag == 'e':
            base = _convert_container(child)
        elif tag == 'lim':
            lim = _convert_container(child)

    return base + '^{' + lim + '}'


def _convert_function(el) -> str:
    """Convert <m:func> — function application (sin x, log x)."""
    fname = ""
    arg = ""

    for child in el:
        tag = _localname(child)
        if tag == 'fname':
            fname = _convert_container(child)
        elif tag == 'e':
            arg = _convert_container(child)

    # Wrap known function names in \operatorname
    fname_clean = fname.strip()
    if fname_clean.lower() in FUNCTION_NAMES:
        return '\\' + fname_clean.lower() + ' ' + arg
    return r'\operatorname{' + fname + '} ' + arg


def _convert_function_name(el) -> str:
    """Convert <m:fname> — function name."""
    return _convert_container(el)


def _convert_delimiter(el) -> str:
    """Convert <m:d> — delimiter (brackets, braces, etc.)."""
    beg = '('
    end = ')'
    sep = ""
    parts = []

    for child in el:
        tag = _localname(child)
        if tag == 'dPr':
            for prop in child:
                ptag = _localname(prop)
                if ptag == 'begChr':
                    val = prop.get(f'{{{NS["m"]}}}val', prop.get('val', '('))
                    beg = DELIMITER_MAP.get(val, val)
                elif ptag == 'endChr':
                    val = prop.get(f'{{{NS["m"]}}}val', prop.get('val', ')'))
                    end = DELIMITER_MAP.get(val, val)
                elif ptag == 'sepChr':
                    val = prop.get(f'{{{NS["m"]}}}val', prop.get('val', '|'))
                    sep = DELIMITER_MAP.get(val, val)
        elif tag == 'e':
            parts.append(_convert_container(child))

    content = (r' ' + sep + r' ').join(parts) if sep else ' '.join(parts)

    # Use \left/\right for auto-sizing
    return r'\left' + beg + ' ' + content + r' \right' + end


def _convert_equation_array(el) -> str:
    """Convert <m:eqArr> — equation array (system of equations)."""
    rows = []
    for child in el:
        if _localname(child) == 'e':
            row_parts = []
            for gc in child:
                row_parts.append(_convert_element(gc))
            rows.append(' & '.join(row_parts) if len(row_parts) > 1 else ''.join(row_parts))

    inner = r' \\ '.join(rows)
    return r'\begin{array}{l} ' + inner + r' \end{array}'


def _convert_matrix(el) -> str:
    """Convert <m:m> — matrix."""
    rows = []

    for child in el:
        if _localname(child) == 'mr':
            rows.append(_convert_matrix_row(child))

    inner = r' \\ '.join(rows)
    return r'\begin{pmatrix} ' + inner + r' \end{pmatrix}'


def _convert_matrix_row(el) -> str:
    """Convert <m:mr> — matrix row."""
    cells = []
    for child in el:
        cells.append(_convert_element(child))
    return ' & '.join(cells)


def _convert_border_box(el) -> str:
    """Convert <m:borderBox> — bordered box."""
    content = _convert_container(el)
    return r'\boxed{' + content + '}'


def _convert_bar(el) -> str:
    """Convert <m:bar> — bar/overline/underline."""
    content = ""
    pos = "top"

    for child in el:
        tag = _localname(child)
        if tag == 'e':
            content = _convert_container(child)
        elif tag == 'barPr':
            for prop in child:
                if _localname(prop) == 'pos':
                    pos = prop.get(f'{{{NS["m"]}}}val', prop.get('val', 'top'))

    if pos == 'top':
        return r'\overline{' + content + '}'
    return r'\underline{' + content + '}'


def _convert_accent(el) -> str:
    """Convert <m:acc> — accent (hat, tilde, bar, etc.)."""
    content = ""
    chr_val = ""

    for child in el:
        tag = _localname(child)
        if tag == 'e':
            content = _convert_container(child)
        elif tag == 'accPr':
            for prop in child:
                if _localname(prop) == 'chr':
                    chr_val = prop.get(f'{{{NS["m"]}}}val', prop.get('val', ''))

    accent_map = {
        '̂': 'hat',
        '̃': 'tilde',
        '̄': 'bar',
        '⃗': 'vec',
        '̇': 'dot',
        '̈': 'ddot',
        '̆': 'breve',
        '̊': 'mathring',
    }

    cmd = accent_map.get(chr_val, 'hat')
    return '\\' + cmd + '{' + content + '}'


def _convert_group_char(el) -> str:
    """Convert <m:groupChr> — group character (brace under/over)."""
    content = ""
    chr_val = ""
    pos = "bot"

    for child in el:
        tag = _localname(child)
        if tag == 'e':
            content = _convert_container(child)
        elif tag == 'groupChrPr':
            for prop in child:
                ptag = _localname(prop)
                if ptag == 'chr':
                    chr_val = prop.get(f'{{{NS["m"]}}}val', prop.get('val', ''))
                elif ptag == 'pos':
                    pos = prop.get(f'{{{NS["m"]}}}val', prop.get('val', 'bot'))

    if pos == 'top':
        return r'\overbrace{' + content + '}'
    return r'\underbrace{' + content + '}'


def _convert_default(el) -> str:
    """Default handler: convert children."""
    parts = []
    if el.text:
        parts.append(el.text)
    for child in el:
        parts.append(_convert_element(child))
        if child.tail:
            parts.append(child.tail)
    return ''.join(parts)


def omml_string_to_latex(xml_string: str) -> Optional[str]:
    """
    Convert an OMML XML string to LaTeX.
    Handles namespaces and root element wrapping.
    """
    try:
        # Add namespace if missing
        if not xml_string.strip().startswith('<?xml') and '<m:oMath' not in xml_string:
            xml_string = f'<m:oMath xmlns:m="{NS["m"]}">{xml_string}</m:oMath>'

        root = ET.fromstring(xml_string)
        return _convert_element(root)
    except ET.ParseError:
        return None


# ── Convenience: extract from python-docx paragraph ─────────────

def extract_equations_from_docx_paragraph(para) -> List[str]:
    """
    Extract all OMML equations from a python-docx paragraph as LaTeX.
    Usage:
        from docx import Document
        doc = Document('paper.docx')
        for para in doc.paragraphs:
            equations = extract_equations_from_docx_paragraph(para)
    """
    equations = []
    try:
        import docx.oxml.ns as ns
        omml_elements = para._element.findall(
            './/' + ns.qn('m:oMath'),
            namespaces=ns.nsmap
        )
        for omml in omml_elements:
            latex = omml_to_latex(omml)
            if latex:
                equations.append(latex)

        # Also check oMathPara (display equations)
        omath_para = para._element.findall(
            './/' + ns.qn('m:oMathPara'),
            namespaces=ns.nsmap
        )
        for omp in omath_para:
            latex = omml_to_latex(omp)
            if latex:
                equations.append(latex)
    except (ImportError, Exception):
        pass

    return equations
