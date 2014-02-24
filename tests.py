#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals, print_function

import unittest, tempfile, os
from groper import OptionsMeta, OptionsUserError, OptionsError
try:
    from configparser import RawConfigParser, NoOptionError
except ImportError:
    from ConfigParser import RawConfigParser, NoOptionError

class GroperTest(unittest.TestCase):

    def setUp(self):
        self.options, self.cmdargs, self.define_opt, self.define_args, self.parse_config, self.parse_args,\
            self.set_defaults, self.verify_all_options, self.init_options, self.generate_sample_config, self.usage = OptionsMeta(lambda s: None)

    def test_define_opt(self):
        self.assertRaises(OptionsError, self.define_opt, '', '')
        self.assertRaises(OptionsError, self.define_opt, '#foobar', 'hello')
        self.assertRaises(OptionsError, self.define_opt, '-foobar', '')
        self.assertRaises(OptionsError, self.define_opt, 'foobar', '~soo')
        
        self.assertRaises(OptionsError, self.define_opt, 'foobar', 'bazbaz', cmd_name=1)
        self.assertRaises(OptionsError, self.define_opt, 'foobar', 'bazbaz', cmd_short_name=1)

        self.assertEqual(self.define_opt('foobar', 'soo'), None)
        self.assertRaises(OptionsError, self.define_opt, 'foobar', 'soo') # Double define
        
        self.assertRaises(OptionsError, self.define_opt, 'foobar', 'config', is_config_file=True)
        self.assertEqual(self.define_opt('foobar', 'config', is_config_file=True, cmd_name='config', cmd_short_name='c'), None)

    def test_parse_args(self):
        self.define_opt('foobar', 'config', is_config_file=True, cmd_name='config', cmd_short_name='c')
        self.define_opt('foobar', 'num', type=int, cmd_name='num', cmd_short_name='n')
        self.define_opt('foobar', 'dec', type=float, cmd_name='dec', cmd_short_name='d')
        self.define_opt('foobar', 'flag', type=bool, cmd_name='flag', cmd_short_name='f')

        self.parse_args(['--config=/tmp/noname.conf', '--num=-1', '--dec=-2.0'])
        self.set_defaults()

        self.assertEqual(self.options.foobar.config, '/tmp/noname.conf')
        self.assertEqual(self.options.foobar.num, -1)
        self.assertAlmostEqual(self.options.foobar.dec, -2.0)
        self.assertEqual(self.options.foobar.flag, False)
        
        self.parse_args(['--config=/tmp/noname.conf', '--num=0', '--dec=0.0', '--flag'])
        self.set_defaults()

        self.assertEqual(self.options.foobar.config, '/tmp/noname.conf')
        self.assertEqual(self.options.foobar.num, 0)
        self.assertAlmostEqual(self.options.foobar.dec, 0.0)
        self.assertEqual(self.options.foobar.flag, True)
        
        self.parse_args(['-c', '/tmp/noname.conf', '-n', '0', '-', '0.0', '-f'])
        self.set_defaults()

        self.assertEqual(self.options.foobar.config, '/tmp/noname.conf')
        self.assertEqual(self.options.foobar.num, 0)
        self.assertAlmostEqual(self.options.foobar.dec, 0.0)
        self.assertEqual(self.options.foobar.flag, True)

    def test_parse_config(self):
        fd, filename = tempfile.mkstemp()
        fp = os.fdopen(fd, 'w')
        try:
            cp = RawConfigParser()
            cp.add_section('sec')
            cp.set('sec', 'foo', 'foo')
            cp.set('sec', 'bar', '-1')
            cp.set('sec', 'baz', '-0.1')
            cp.set('sec', 'hum', 'yes')
            cp.set('sec', 'dum', 'no')

            cp.write(fp)
            fp.close()

            self.define_opt('sec', 'foo')
            self.define_opt('sec', 'bar', type=int)
            self.define_opt('sec', 'baz', type=float)
            self.define_opt('sec', 'hum', type=bool)
            self.define_opt('sec', 'dum', type=bool)

            self.parse_config(filename)
            self.verify_all_options()

            self.assertEqual(self.options.sec.foo, 'foo')
            self.assertEqual(self.options.sec.bar, -1)
            self.assertAlmostEqual(self.options.sec.baz, -0.1)
            self.assertEqual(self.options.sec.hum, True)
            self.assertEqual(self.options.sec.dum, False)
        finally:
            os.unlink(filename)

    def test_defaults(self):
        self.define_opt('sec', 'foo', default='fõõ')
        self.define_opt('sec', 'bar', type=int, default=-1)
        self.define_opt('sec', 'baz', type=float, default=-0.1)
        self.define_opt('sec', 'hum', type=bool, default=True)
        self.define_opt('sec', 'dum', type=bool, default=False)
        self.define_opt('sec', 'nop')

        self.set_defaults()

        self.assertEqual(self.options.sec.foo, 'fõõ')
        self.assertEqual(self.options.sec.bar, -1)
        self.assertAlmostEqual(self.options.sec.baz, -0.1)
        self.assertEqual(self.options.sec.hum, True)
        self.assertEqual(self.options.sec.dum, False)
        self.assertTrue(not hasattr(self.options.sec, 'nop'))

    def test_init_options(self):
        fd, filename = tempfile.mkstemp()
        try:

            conf = '''
                [sec]
                foo = cõnf-fõõ
                nop = cõnf-nõp
                
                [con]
                foo = cõnf-fõõ
                bar = -2
                baz = -0.2
                hum = False
                dum = True
                nop = cõnf-nõp
                
                [cmd]
                foo = cõnf-fõõ
            '''

            fp = os.fdopen(fd, 'wb')
            data = '\n'.join([s.strip() for s in conf.split('\n')])
            fp.write(data.encode('utf-8'))
            fp.close()

            self.define_opt('sec', 'foo', default='fõõ')
            self.define_opt('sec', 'bar', type=int, default=-1)
            self.define_opt('sec', 'baz', type=float, default=-0.1)
            self.define_opt('sec', 'hum', type=bool, default=True)
            self.define_opt('sec', 'dum', type=bool, default=False)
            self.define_opt('sec', 'nop')

            self.define_opt('con', 'foo', default='fõõ')
            self.define_opt('con', 'bar', type=int, default=-1)
            self.define_opt('con', 'baz', type=float, default=-0.1)
            self.define_opt('con', 'hum', type=bool, default=True)
            self.define_opt('con', 'dum', type=bool, default=False)
            self.define_opt('con', 'nop')

            self.define_opt('cmd', 'config', cmd_name='config', cmd_short_name='c', is_config_file=True)
            self.define_opt('cmd', 'help', type=bool, cmd_name='help', cmd_short_name='h', is_help=True, cmd_group='help')

            self.define_opt('cmd', 'foo', default='fõõ', cmd_name='foo', cmd_short_name='f')
            self.define_opt('cmd', 'bar', type=int, default=-1, cmd_name='bar')
            self.define_opt('cmd', 'baz', type=float, default=-0.1, cmd_short_name='z')
            self.define_opt('cmd', 'hum', type=bool, default=True, cmd_name='hum')
            self.define_opt('cmd', 'dum', type=bool, default=False, cmd_short_name='d')
            self.define_opt('cmd', 'nop', cmd_name='nop')

            self.assertRaises(SystemExit, self.init_options, ['--help'])
            self.assertRaises(SystemExit, self.init_options, [])
            self.assertRaises(SystemExit, self.init_options, ['--config={0}'.format(filename)])
            self.init_options(['--config={0}'.format(filename), '--nop=cmd-nop', '--bar=-15', '-z', '-0.3', '--hum', '-d'])

            self.assertEqual(self.options.sec.foo, 'cõnf-fõõ')
            self.assertEqual(self.options.sec.bar, -1)
            self.assertAlmostEqual(self.options.sec.baz, -0.1)
            self.assertEqual(self.options.sec.hum, True)
            self.assertEqual(self.options.sec.dum, False)
            self.assertEqual(self.options.sec.nop, 'cõnf-nõp')

            self.assertEqual(self.options.con.foo, 'cõnf-fõõ')
            self.assertEqual(self.options.con.bar, -2)
            self.assertAlmostEqual(self.options.con.baz, -0.2)
            self.assertEqual(self.options.con.hum, False)
            self.assertEqual(self.options.con.dum, True)
            self.assertEqual(self.options.con.nop, 'cõnf-nõp')

            self.assertEqual(self.options.cmd.foo, 'cõnf-fõõ')
            self.assertEqual(self.options.cmd.bar, -15)
            self.assertAlmostEqual(self.options.cmd.baz, -0.3)
            self.assertEqual(self.options.cmd.hum, True)
            self.assertEqual(self.options.cmd.dum, True)
            self.assertEqual(self.options.cmd.nop, 'cmd-nop')

        finally:
            os.unlink(filename)
    
    def test_init_options_with_default_config_file(self):
        fd, filename = tempfile.mkstemp()
        try:

            conf = '''
                [sec]
                foo = cõnf-fõõ
            '''

            fp = os.fdopen(fd, 'wb')
            data = '\n'.join([s.strip() for s in conf.split('\n')])
            fp.write(data.encode('utf-8'))
            fp.close()

            self.define_opt('sec', 'foo', default='fõõ')
            self.define_opt('cmd', 'config', cmd_name='config', cmd_short_name='c', is_config_file=True, default=filename)
            self.define_opt('cmd', 'help', type=bool, cmd_name='help', cmd_short_name='h', is_help=True, cmd_group='help')

            self.init_options()

            self.assertEqual(self.options.sec.foo, 'cõnf-fõõ')
        finally:
            os.unlink(filename)
    
    def test_generate_sample_config(self):
        filename = tempfile.mkstemp()[1]
        try:
            self.define_opt('sec', 'foo', default='foo')
            self.define_opt('sec', 'bar', type=int, default=-1)
            self.define_opt('sec', 'baz', type=float, default=-0.1)
            self.define_opt('sec', 'hum', type=bool, default=True)
            self.define_opt('sec', 'dum', type=bool, default=False)

            with open(filename, 'w') as fp:
                fp.write(self.generate_sample_config())

            self.parse_config(filename)

            self.assertEqual(self.options.sec.foo, 'foo')
            self.assertEqual(self.options.sec.bar, -1)
            self.assertAlmostEqual(self.options.sec.baz, -0.1)
            self.assertEqual(self.options.sec.hum, True)
            self.assertEqual(self.options.sec.dum, False)

        finally:
            os.unlink(filename)
    
    def test_args(self):
        self.define_opt('sec', 'foo', default='foo', cmd_name='foo')
        self.define_opt('sec', 'bar', type=int, default=-1, cmd_short_name='b')

        self.define_args((-2, 'file'))
        self.parse_args(['--foo=cmdfoo', '-b', '-2'])
        self.assertRaises(OptionsUserError, self.verify_all_options)
        
        self.define_args(('file1', 'file2', 'file3'))
        self.parse_args(['--foo=cmdfoo', '-b', '-2'])
        self.assertRaises(OptionsUserError, self.verify_all_options)
        
        self.define_args(('file1', 'file2', 'file3'))
        self.parse_args(['--foo=cmdfoo', '-b', '-2', 'a', 'b', 'c'])
        self.verify_all_options()
            
        self.assertEqual(self.options.sec.foo, 'cmdfoo')
        self.assertEqual(self.options.sec.bar, -2)
        self.assertEqual(self.cmdargs, ['a', 'b', 'c'])

tests_all = unittest.TestLoader().loadTestsFromTestCase(GroperTest)

if __name__ == '__main__':
    unittest.TextTestRunner(verbosity=2).run(tests_all)
