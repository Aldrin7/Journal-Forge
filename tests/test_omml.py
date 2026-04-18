#!/usr/bin/env python3
"""
PaperForge — OMML to LaTeX Conversion Tests
Tests the pure-Python OMML parser with various equation types.
"""
import sys
import pathlib

PROJECT_ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

PASS = "✅ PASS"
FAIL = "❌ FAIL"


def test(name, passed, msg=""):
    status = PASS if passed else FAIL
    print(f"  {status} {name}" + (f" — {msg}" if msg else ""))
    return passed


def main():
    from src.ingestion.omml_to_latex import omml_to_latex, omml_string_to_latex

    all_passed = True
    print("=" * 60)
    print("  OMML → LaTeX Conversion Test Suite")
    print("=" * 60)

    # Test 1: Simple fraction
    print("\n[1] Fractions")
    xml = '''<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">
        <m:f>
            <m:num><m:r><m:t>a</m:t></m:r></m:num>
            <m:den><m:r><m:t>b</m:t></m:r></m:den>
        </m:f>
    </m:oMath>'''
    result = omml_string_to_latex(xml)
    ok = result is not None and r'\frac' in result
    test("Fraction", ok, f"Result: {result}")
    all_passed = all_passed and ok

    # Test 2: Superscript
    print("\n[2] Superscripts")
    xml = '''<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">
        <m:sSup>
            <m:e><m:r><m:t>x</m:t></m:r></m:e>
            <m:sup><m:r><m:t>2</m:t></m:r></m:sup>
        </m:sSup>
    </m:oMath>'''
    result = omml_string_to_latex(xml)
    ok = result is not None and '^{' in result
    test("Superscript", ok, f"Result: {result}")
    all_passed = all_passed and ok

    # Test 3: Subscript
    print("\n[3] Subscripts")
    xml = '''<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">
        <m:sSub>
            <m:e><m:r><m:t>x</m:t></m:r></m:e>
            <m:sub><m:r><m:t>1</m:t></m:r></m:sub>
        </m:sSub>
    </m:oMath>'''
    result = omml_string_to_latex(xml)
    ok = result is not None and '_{' in result
    test("Subscript", ok, f"Result: {result}")
    all_passed = all_passed and ok

    # Test 4: Square root
    print("\n[4] Radicals")
    xml = '''<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">
        <m:rad>
            <m:deg><m:r><m:t>3</m:t></m:r></m:deg>
            <m:e><m:r><m:t>x</m:t></m:r></m:e>
        </m:rad>
    </m:oMath>'''
    result = omml_string_to_latex(xml)
    ok = result is not None and r'\sqrt' in result
    test("Nth root", ok, f"Result: {result}")
    all_passed = all_passed and ok

    # Test 5: Summation
    print("\n[5] N-ary operators")
    xml = '''<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">
        <m:nary>
            <m:naryPr><m:chr m:val="∑"/></m:naryPr>
            <m:sub><m:r><m:t>i=1</m:t></m:r></m:sub>
            <m:sup><m:r><m:t>n</m:t></m:r></m:sup>
            <m:e><m:r><m:t>x_i</m:t></m:r></m:e>
        </m:nary>
    </m:oMath>'''
    result = omml_string_to_latex(xml)
    ok = result is not None and r'\sum' in result
    test("Summation", ok, f"Result: {result}")
    all_passed = all_passed and ok

    # Test 6: Delimiter
    print("\n[6] Delimiters")
    xml = '''<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">
        <m:d>
            <m:dPr><m:begChr m:val="("/><m:endChr m:val=")"/></m:dPr>
            <m:e><m:r><m:t>a + b</m:t></m:r></m:e>
        </m:d>
    </m:oMath>'''
    result = omml_string_to_latex(xml)
    ok = result is not None and r'\left' in result
    test("Parentheses", ok, f"Result: {result}")
    all_passed = all_passed and ok

    # Test 7: Matrix
    print("\n[7] Matrix")
    xml = '''<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">
        <m:m>
            <m:mr><m:e><m:r><m:t>a</m:t></m:r></m:e><m:e><m:r><m:t>b</m:t></m:r></m:e></m:mr>
            <m:mr><m:e><m:r><m:t>c</m:t></m:r></m:e><m:e><m:r><m:t>d</m:t></m:r></m:e></m:mr>
        </m:m>
    </m:oMath>'''
    result = omml_string_to_latex(xml)
    ok = result is not None and r'\begin{pmatrix}' in result
    test("Matrix", ok, f"Result: {result}")
    all_passed = all_passed and ok

    # Test 8: Accent (hat)
    print("\n[8] Accents")
    xml = '''<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">
        <m:acc>
            <m:accPr><m:chr m:val="̂"/></m:accPr>
            <m:e><m:r><m:t>x</m:t></m:r></m:e>
        </m:acc>
    </m:oMath>'''
    result = omml_string_to_latex(xml)
    ok = result is not None and r'\hat' in result
    test("Hat accent", ok, f"Result: {result}")
    all_passed = all_passed and ok

    # Test 9: Bar/overline
    print("\n[9] Bar/Overline")
    xml = '''<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">
        <m:bar>
            <m:barPr><m:pos m:val="top"/></m:barPr>
            <m:e><m:r><m:t>x</m:t></m:r></m:e>
        </m:bar>
    </m:oMath>'''
    result = omml_string_to_latex(xml)
    ok = result is not None and r'\overline' in result
    test("Overline", ok, f"Result: {result}")
    all_passed = all_passed and ok

    # Test 10: Combined equation (E = mc^2)
    print("\n[10] Complex equation")
    xml = '''<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">
        <m:r><m:t>E = </m:t></m:r>
        <m:sSup>
            <m:e><m:r><m:t>mc</m:t></m:r></m:e>
            <m:sup><m:r><m:t>2</m:t></m:r></m:sup>
        </m:sSup>
    </m:oMath>'''
    result = omml_string_to_latex(xml)
    ok = result is not None and 'E' in result and '^{' in result
    test("E = mc²", ok, f"Result: {result}")
    all_passed = all_passed and ok

    # Summary
    print(f"\n{'=' * 60}")
    if all_passed:
        print(f"  ✅ ALL OMML TESTS PASSED")
    else:
        print(f"  ❌ SOME OMML TESTS FAILED")
    print(f"{'=' * 60}\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
