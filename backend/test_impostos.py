#!/usr/bin/env python3

# Test script for valor_total_impostos extraction
import re
from typing import Optional

def find_total_impostos(text: str) -> Optional[float]:
    """Extract total tax value from fiscal document text."""
    if not text:
        return None
    
    # Look for explicit tax total patterns (Brazilian format)
    tax_patterns = [
        r'(?:vlr\s+aprox\s+dos\s+tributos?|valor\s+aproximado\s+dos\s+tributos?|total\s+tributos?)\s*:?\s*R?\$?\s*([0-9]+[,\.][0-9]{2})',
        r'(?:impostos?\s+totais?|total\s+de\s+impostos?)\s*:?\s*R?\$?\s*([0-9]+[,\.][0-9]{2})',
        r'R\$\s*([0-9]+[,\.][0-9]{2})\s+(?:federal|estadual|municipal)'
    ]
    
    for pattern in tax_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            print(f"Pattern matched: {pattern}")
            print(f"Matches: {matches}")
            # Get the first valid tax value
            for match in matches:
                try:
                    s = match.replace('.', '').replace(',', '.')
                    val = float(s)
                    print(f"Converted value: {val}")
                    if 0 < val < 100000:  # Reasonable tax value range
                        return val
                except Exception as e:
                    print(f"Error converting {match}: {e}")
                    continue
    
    # Look for individual tax components to sum
    tax_components = []
    individual_patterns = [
        r'R\$\s*([0-9]+[,\.][0-9]{2})\s+federal',
        r'R\$\s*([0-9]+[,\.][0-9]{2})\s+estadual',
        r'R\$\s*([0-9]+[,\.][0-9]{2})\s+municipal',
        r'icms\s*:?\s*R?\$?\s*([0-9]+[,\.][0-9]{2})',
        r'ipi\s*:?\s*R?\$?\s*([0-9]+[,\.][0-9]{2})',
        r'pis\s*:?\s*R?\$?\s*([0-9]+[,\.][0-9]{2})',
        r'cofins\s*:?\s*R?\$?\s*([0-9]+[,\.][0-9]{2})'
    ]
    
    for pattern in individual_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            print(f"Individual pattern matched: {pattern}")
            print(f"Individual matches: {matches}")
        for match in matches:
            try:
                s = match.replace('.', '').replace(',', '.')
                val = float(s)
                if 0 < val < 100000:
                    tax_components.append(val)
            except Exception:
                continue
    
    # Return sum of individual components if found
    if tax_components:
        print(f"Tax components found: {tax_components}")
        return sum(tax_components)
    
    return None

# Test with the actual text from the document
test_text = """Vlr Aprox dos Tributos: R$ 56,49 Federal  / R$ 50,40 Estadual - Fonte:
IBPT"""

print("Testing with:", repr(test_text))
result = find_total_impostos(test_text)
print(f"Result: {result}")