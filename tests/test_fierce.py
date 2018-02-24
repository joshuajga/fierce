#!/usr/bin/env python

import ipaddress
import io
import textwrap
import unittest
import unittest.mock

import dns.exception
import dns.name
import dns.resolver

from fierce import fierce


class TestFierce(unittest.TestCase):

    def test_concatenate_subdomains_empty(self):
        domain = dns.name.from_text("example.com.")
        subdomains = []

        result = fierce.concatenate_subdomains(domain, subdomains)
        expected = dns.name.from_text("example.com.")

        self.assertEqual(expected, result)

    def test_concatenate_subdomains_single_subdomain(self):
        domain = dns.name.from_text("example.com.")
        subdomains = ["sd1"]

        result = fierce.concatenate_subdomains(domain, subdomains)
        expected = dns.name.from_text("sd1.example.com.")

        self.assertEqual(expected, result)

    def test_concatenate_subdomains_multiple_subdomains(self):
        domain = dns.name.from_text("example.com.")
        subdomains = ["sd1", "sd2"]

        result = fierce.concatenate_subdomains(domain, subdomains)
        expected = dns.name.from_text("sd1.sd2.example.com.")

        self.assertEqual(expected, result)

    def test_concatenate_subdomains_makes_root(self):
        # Domain is missing '.' at the end
        domain = dns.name.from_text("example.com")
        subdomains = []

        result = fierce.concatenate_subdomains(domain, subdomains)
        expected = dns.name.from_text("example.com.")

        self.assertEqual(expected, result)

    def test_concatenate_subdomains_single_sub_subdomain(self):
        domain = dns.name.from_text("example.com.")
        subdomains = ["sd1.sd2"]

        result = fierce.concatenate_subdomains(domain, subdomains)
        expected = dns.name.from_text("sd1.sd2.example.com.")

        self.assertEqual(expected, result)

    def test_concatenate_subdomains_multiple_sub_subdomain(self):
        domain = dns.name.from_text("example.com.")
        subdomains = ["sd1.sd2", "sd3.sd4"]

        result = fierce.concatenate_subdomains(domain, subdomains)
        expected = dns.name.from_text("sd1.sd2.sd3.sd4.example.com.")

        self.assertEqual(expected, result)

    def test_concatenate_subdomains_fqdn_subdomain(self):
        domain = dns.name.from_text("example.")
        subdomains = ["sd1.sd2."]

        result = fierce.concatenate_subdomains(domain, subdomains)
        expected = dns.name.from_text("sd1.sd2.example.")

        self.assertEqual(expected, result)

    def test_traverse_expander_basic(self):
        ip = ipaddress.IPv4Address('192.168.1.1')
        expand = 1

        result = fierce.traverse_expander(ip, expand)
        expected = [
            ipaddress.IPv4Address('192.168.1.0'),
            ipaddress.IPv4Address('192.168.1.1'),
            ipaddress.IPv4Address('192.168.1.2'),
        ]

        self.assertEqual(expected, result)

    def test_traverse_expander_no_cross_lower_boundary(self):
        ip = ipaddress.IPv4Address('192.168.1.1')
        expand = 2

        result = fierce.traverse_expander(ip, expand)
        expected = [
            ipaddress.IPv4Address('192.168.1.0'),
            ipaddress.IPv4Address('192.168.1.1'),
            ipaddress.IPv4Address('192.168.1.2'),
            ipaddress.IPv4Address('192.168.1.3'),
        ]

        self.assertEqual(expected, result)

    def test_traverse_expander_no_cross_upper_boundary(self):
        ip = ipaddress.IPv4Address('192.168.1.254')
        expand = 2

        result = fierce.traverse_expander(ip, expand)
        expected = [
            ipaddress.IPv4Address('192.168.1.252'),
            ipaddress.IPv4Address('192.168.1.253'),
            ipaddress.IPv4Address('192.168.1.254'),
            ipaddress.IPv4Address('192.168.1.255'),
        ]

        self.assertEqual(expected, result)

    def test_wide_expander_basic(self):
        ip = ipaddress.IPv4Address('192.168.1.50')

        result = fierce.wide_expander(ip)

        expected = [
            ipaddress.IPv4Address('192.168.1.{}'.format(i))
            for i in range(256)
        ]

        self.assertEqual(expected, result)

    def test_wide_expander_lower_boundary(self):
        ip = ipaddress.IPv4Address('192.168.1.0')

        result = fierce.wide_expander(ip)

        expected = [
            ipaddress.IPv4Address('192.168.1.{}'.format(i))
            for i in range(256)
        ]

        self.assertEqual(expected, result)

    def test_wide_expander_upper_boundary(self):
        ip = ipaddress.IPv4Address('192.168.1.255')

        result = fierce.wide_expander(ip)

        expected = [
            ipaddress.IPv4Address('192.168.1.{}'.format(i))
            for i in range(256)
        ]

        self.assertEqual(expected, result)

    def test_recursive_query_basic_failure(self):
        resolver = dns.resolver.Resolver()
        domain = dns.name.from_text('example.com.')
        record_type = 'NS'

        with unittest.mock.patch.object(fierce, 'query', return_value=None) as mock_method:
            result = fierce.recursive_query(resolver, domain, record_type=record_type)

        expected = [
            unittest.mock.call(resolver, 'example.com.', record_type),
            unittest.mock.call(resolver, 'com.', record_type),
            unittest.mock.call(resolver, '', record_type),
        ]

        mock_method.assert_has_calls(expected)
        self.assertIsNone(result)

    def test_recursive_query_long_domain_failure(self):
        resolver = dns.resolver.Resolver()
        domain = dns.name.from_text('sd1.sd2.example.com.')
        record_type = 'NS'

        with unittest.mock.patch.object(fierce, 'query', return_value=None) as mock_method:
            result = fierce.recursive_query(resolver, domain, record_type=record_type)

        expected = [
            unittest.mock.call(resolver, 'sd1.sd2.example.com.', record_type),
            unittest.mock.call(resolver, 'sd2.example.com.', record_type),
            unittest.mock.call(resolver, 'example.com.', record_type),
            unittest.mock.call(resolver, 'com.', record_type),
            unittest.mock.call(resolver, '', record_type),
        ]

        mock_method.assert_has_calls(expected)
        self.assertIsNone(result)

    def test_recursive_query_basic_success(self):
        resolver = dns.resolver.Resolver()
        domain = dns.name.from_text('example.com.')
        record_type = 'NS'
        good_response = unittest.mock.MagicMock()
        side_effect = [
            None,
            good_response,
            None,
        ]

        with unittest.mock.patch.object(fierce, 'query', side_effect=side_effect) as mock_method:
            result = fierce.recursive_query(resolver, domain, record_type=record_type)

        expected = [
            unittest.mock.call(resolver, 'example.com.', record_type),
            unittest.mock.call(resolver, 'com.', record_type),
        ]

        mock_method.assert_has_calls(expected)
        self.assertEqual(result, good_response)

    def test_query_nxdomain(self):
        resolver = dns.resolver.Resolver()
        domain = dns.name.from_text('example.com.')

        with unittest.mock.patch.object(resolver, 'query', side_effect=dns.resolver.NXDOMAIN()):
            result = fierce.query(resolver, domain)

        self.assertIsNone(result)

    def test_query_no_nameservers(self):
        resolver = dns.resolver.Resolver()
        domain = dns.name.from_text('example.com.')

        with unittest.mock.patch.object(resolver, 'query', side_effect=dns.resolver.NoNameservers()):
            result = fierce.query(resolver, domain)

        self.assertIsNone(result)

    def test_query_timeout(self):
        resolver = dns.resolver.Resolver()
        domain = dns.name.from_text('example.com.')

        with unittest.mock.patch.object(resolver, 'query', side_effect=dns.exception.Timeout()):
            result = fierce.query(resolver, domain)

        self.assertIsNone(result)

    def test_zone_transfer_connection_error(self):
        address = 'test'
        domain = dns.name.from_text('example.com.')

        with unittest.mock.patch.object(fierce.dns.zone, 'from_xfr', side_effect=ConnectionError()):
            result = fierce.zone_transfer(address, domain)

        self.assertIsNone(result)

    def test_zone_transfer_eof_error(self):
        address = 'test'
        domain = dns.name.from_text('example.com.')

        with unittest.mock.patch.object(fierce.dns.zone, 'from_xfr', side_effect=EOFError()):
            result = fierce.zone_transfer(address, domain)

        self.assertIsNone(result)

    def test_zone_transfer_timeout_error(self):
        address = 'test'
        domain = dns.name.from_text('example.com.')

        with unittest.mock.patch.object(fierce.dns.zone, 'from_xfr', side_effect=TimeoutError()):
            result = fierce.zone_transfer(address, domain)

        self.assertIsNone(result)

    def test_zone_transfer_form_error(self):
        address = 'test'
        domain = dns.name.from_text('example.com.')

        with unittest.mock.patch.object(fierce.dns.zone, 'from_xfr', side_effect=dns.exception.FormError()):
            result = fierce.zone_transfer(address, domain)

        self.assertIsNone(result)

    def test_find_nearby_empty(self):
        resolver = 'unused'
        ips = []

        result = fierce.find_nearby(resolver, ips)
        expected = {}

        self.assertEqual(expected, result)

    def test_find_nearby_basic(self):
        resolver = 'unused'
        ips = [
            ipaddress.IPv4Address('192.168.1.0'),
            ipaddress.IPv4Address('192.168.1.1'),
        ]
        side_effect = [
            'sd1.example.com.',
            'sd2.example.com.',
        ]

        with unittest.mock.patch.object(fierce, 'reverse_query', side_effect=side_effect):
            result = fierce.find_nearby(resolver, ips)

        expected = {
            '192.168.1.0': 'sd1.example.com.',
            '192.168.1.1': 'sd2.example.com.',
        }

        self.assertEqual(expected, result)

    def test_find_nearby_filter_func(self):
        resolver = 'unused'
        ips = [
            ipaddress.IPv4Address('192.168.1.0'),
            ipaddress.IPv4Address('192.168.1.1'),
        ]

        # Simply getting a dns.resolver.Answer with a specific result was
        # more difficult than I'd like, let's just go with this less than
        # ideal approach for now
        class MockAnswer(object):
            def __init__(self, response):
                self.response = response

            def to_text(self):
                return self.response

        returned_answer = [MockAnswer('sd1.example.com.')]

        side_effect = [
            returned_answer,
            [MockAnswer('sd2.example.com.')],
        ]

        def filter_func(reverse_result):
            return reverse_result == 'sd1.example.com.'

        with unittest.mock.patch.object(fierce, 'reverse_query', side_effect=side_effect):
            result = fierce.find_nearby(resolver, ips, filter_func=filter_func)

        expected = {
            '192.168.1.0': returned_answer,
        }

        self.assertEqual(expected, result)

    def test_print_subdomain_result_basic(self):
        url = 'example.com'
        ip = '192.168.1.0'

        with io.StringIO() as stream:
            fierce.print_subdomain_result(url, ip, stream=stream)
            result = stream.getvalue()

        expected = 'Found: example.com (192.168.1.0)\n'

        self.assertEqual(expected, result)

    def test_print_subdomain_result_nearby(self):
        url = 'example.com'
        ip = '192.168.1.0'
        nearby = {'192.168.1.1': 'nearby.com'}

        with io.StringIO() as stream:
            fierce.print_subdomain_result(url, ip, nearby=nearby, stream=stream)
            result = stream.getvalue()

        expected = textwrap.dedent('''
            Found: example.com (192.168.1.0)
            Nearby:
            {'192.168.1.1': 'nearby.com'}
        ''').lstrip()

        self.assertEqual(expected, result)

    def test_print_subdomain_result_http_header(self):
        url = 'example.com'
        ip = '192.168.1.0'
        http_connection_headers = {'HTTP HEADER': 'value'}

        with io.StringIO() as stream:
            fierce.print_subdomain_result(
                url,
                ip,
                http_connection_headers=http_connection_headers,
                stream=stream
            )
            result = stream.getvalue()

        expected = textwrap.dedent('''
            Found: example.com (192.168.1.0)
            HTTP connected:
            {'HTTP HEADER': 'value'}
        ''').lstrip()

        self.assertEqual(expected, result)

    def test_print_subdomain_result_both(self):
        url = 'example.com'
        ip = '192.168.1.0'
        http_connection_headers = {'HTTP HEADER': 'value'}
        nearby = {'192.168.1.1': 'nearby.com'}

        with io.StringIO() as stream:
            fierce.print_subdomain_result(
                url,
                ip,
                http_connection_headers=http_connection_headers,
                nearby=nearby,
                stream=stream
            )
            result = stream.getvalue()

        expected = textwrap.dedent('''
            Found: example.com (192.168.1.0)
            HTTP connected:
            {'HTTP HEADER': 'value'}
            Nearby:
            {'192.168.1.1': 'nearby.com'}
        ''').lstrip()

        self.assertEqual(expected, result)


if __name__ == "__main__":
    unittest.main()
