#!/usr/bin/env python3
import json
import sys
from xml.etree.ElementTree import Element, SubElement, ElementTree
from datetime import datetime


def convert_trivy_to_junit(json_file, xml_file):
    with open(json_file, 'r') as f:
        trivy_data = json.load(f)

    testsuites = Element('testsuites')

    # Get metadata
    artifact_name = trivy_data.get('ArtifactName', 'unknown')
    artifact_type = trivy_data.get('ArtifactType', 'unknown')

    testsuite = SubElement(testsuites, 'testsuite', {
        'name': f'Trivy Security Scan: {artifact_name}',
        'timestamp': datetime.utcnow().isoformat(),
        'tests': '0',
        'failures': '0',
        'errors': '0',
        'skipped': '0'
    })

    # Add properties
    properties = SubElement(testsuite, 'properties')
    SubElement(properties, 'property', {
        'name': 'artifact_name',
        'value': artifact_name
    })
    SubElement(properties, 'property', {
        'name': 'artifact_type',
        'value': artifact_type
    })

    test_count = 0
    failure_count = 0

    results = trivy_data.get('Results', [])
    for result in results:
        target = result.get('Target', 'unknown')
        result_type = result.get('Type', 'unknown')
        vulnerabilities = result.get('Vulnerabilities', [])

        if not vulnerabilities:
            # Add a passing test case if no vulnerabilities found
            test_count += 1
            testcase = SubElement(testsuite, 'testcase', {
                'name': f'{target}: No vulnerabilities found',
                'classname': f'trivy.{result_type}'
            })
            continue

        for vuln in vulnerabilities:
            test_count += 1
            vuln_id = vuln.get('VulnerabilityID', 'UNKNOWN')
            severity = vuln.get('Severity', 'UNKNOWN')
            pkg_name = vuln.get('PkgName', 'unknown')
            installed_version = vuln.get('InstalledVersion', 'unknown')
            fixed_version = vuln.get('FixedVersion', 'Not fixed')
            title = vuln.get('Title', vuln_id)

            testcase = SubElement(testsuite, 'testcase', {
                'name': f"{pkg_name}@{installed_version}: {vuln_id}",
                'classname': f'trivy.{result_type}.{target}'
            })

            # Build detailed message
            description = vuln.get('Description', 'No description available')
            primary_url = vuln.get('PrimaryURL', '')
            references = vuln.get('References', [])
            cvss = vuln.get('CVSS', {})

            details = []
            details.append(f"Vulnerability: {vuln_id}")
            details.append(f"Severity: {severity}")
            details.append(f"Package: {pkg_name}")
            details.append(f"Installed Version: {installed_version}")
            details.append(f"Fixed Version: {fixed_version}")
            details.append(f"\nTitle: {title}")
            details.append(f"\nDescription:\n{description}")

            if cvss:
                for vendor, data in cvss.items():
                    if isinstance(data, dict):
                        score = data.get('V3Score', data.get('V2Score', 'N/A'))
                        details.append(f"\nCVSS {vendor}: {score}")

            if primary_url:
                details.append(f"\nPrimary URL: {primary_url}")

            if references:
                details.append(f"\nReferences:")
                for ref in references[:5]:  # Limit to first 5 references
                    details.append(f"  - {ref}")

            message_text = '\n'.join(details)

            # Mark as failure if HIGH or CRITICAL
            if severity in ['HIGH', 'CRITICAL']:
                failure_count += 1
                failure = SubElement(testcase, 'failure', {
                    'message': f"{severity}: {vuln_id} in {pkg_name}@{installed_version} (fixed in {fixed_version})",
                    'type': severity
                })
                failure.text = message_text
            else:
                # Add as system-out for non-critical issues
                system_out = SubElement(testcase, 'system-out')
                system_out.text = message_text

    # Update counts
    testsuite.set('tests', str(test_count))
    testsuite.set('failures', str(failure_count))

    # Write to file with pretty formatting
    tree = ElementTree(testsuites)
    indent_xml(testsuites)
    tree.write(xml_file, encoding='utf-8', xml_declaration=True)

    # Print summary
    print(f"Trivy to JUnit conversion complete:")
    print(f"  Total tests: {test_count}")
    print(f"  Failures: {failure_count}")
    print(f"  Output: {xml_file}")


def indent_xml(elem, level=0):
    """Add pretty-print indentation to XML"""
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for child in elem:
            indent_xml(child, level + 1)
        if not child.tail or not child.tail.strip():
            child.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <input.json> <output.xml>")
        sys.exit(1)

    convert_trivy_to_junit(sys.argv[1], sys.argv[2])
