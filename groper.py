from ConfigParser import SafeConfigParser, NoOptionError
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

import getopt, os.path, sys, re

class OptionObject(object):
    def __init__(self, **kwargs):
        for key, val in kwargs.iteritems():
            setattr(self, key, val)

class OptionsError(Exception): pass
class OptionsUserError(Exception): pass

def OptionsMeta(print_func=None):
    '''Creates a private scope for the options manupulation functions and returns them.

    This function us used to create a module-wide global options object and its 
    manipulation functions. It may be used to generate local options objects, for 
    example for unit testing.
    '''

    print_func = print_func or (lambda s: sys.stdout.write('%s\n' % s))

    option_definitions = {}
    cp = SafeConfigParser()
    adapters = {
        bool: cp.getboolean,
        float: cp.getfloat,
        int: cp.getint,
    }

    config_file_def = {
        'section': None,
        'optname': None,
        'filename': None,
    }

    # Variables we will return
    options = OptionObject()
    cmdargs = []
    cmdarg_defs = {
        'count': None,
        'args': None,
    }
    _type = type

    def generate_sample_config():
        '''Returns a string containing a sample configuration file based on the defined options.'''
        
        cp = SafeConfigParser()
        for section in option_definitions:
            for name, opt in option_definitions[section].iteritems():
                if opt.cmd_only:
                    continue

                if not cp.has_section(section):
                    cp.add_section(section)
                cp.set(section, name if hasattr(opt, 'default') else '#%s' % name, unicode(opt.default) if hasattr(opt, 'default') else '<%s>' % name.upper())

        f = StringIO()
        cp.write(f)
        result = f.getvalue()
        f.close()
        return result

    def _option_usage(option):
        '''Create an option usage line part based on option definition.
        
            Returns a tuple of (short_str, long_str) to be added.
        '''
        s, l = None, None

        wrap_optional = lambda option, s: s if option.required else ('[%s]' % s) 

        if option.cmd_short_name:
            if option.type != bool:
                s = wrap_optional(option, '-%s <%s>' % (option.cmd_short_name, option.cmd_name or option.name))
            else:
                s = wrap_optional(option, '-%s' % option.cmd_short_name)
        elif option.cmd_name and option.required:
            if option.type != bool:
                s = wrap_optional(option, '--%s=<%s>' % (option.cmd_name, option.cmd_name or option.name))
            else:
                s = wrap_optional(option, '--%s' % option.cmd_name)
       
        
        if option.cmd_name:
            if option.type != bool:
                l = wrap_optional(option, '--%s=<%s>' % (option.cmd_name, option.cmd_name or option.name))
            else:
                l = wrap_optional(option, '--%s' % option.cmd_name)
        elif option.cmd_short_name and option.required:
            if option.type != bool:
                l = wrap_optional(option, '-%s <%s>' % (option.cmd_short_name, option.cmd_name or option.name))
            else:
                l = wrap_optional(option, '-%s' % option.cmd_short_name)

        return s, l

    def _args_usage(cmdargs_def):
        if cmdarg_defs['count'] == -1:
            return '[%s] ...' %  cmdarg_defs['args'][0]
        elif cmdarg_defs['count'] == -2:
            return '<%s> [%s] ...' %  (cmdarg_defs['args'][0], cmdarg_defs['args'][0])
        elif cmdarg_defs['args']:
            return ' '.join(map(lambda s: '<%s>' % s, cmdarg_defs['args']))

    def usage(cmd_name=None):
        '''Returns usage/help string based on defined options.'''

        cmd_name = cmd_name or os.path.basename(sys.argv[0])
        
        lines = ['Usage:', '',]

        # Group all options
        cmd_options = {}
        for section in option_definitions:
            for name, opt in option_definitions[section].iteritems():
                if opt.cmd_name or opt.cmd_short_name:
                    if opt.cmd_group not in cmd_options:
                        cmd_options[opt.cmd_group] = []
                    cmd_options[opt.cmd_group].append(opt)

        if not cmd_options and cmdarg_defs['count']:
            arg_line = _args_usage(cmdarg_defs)
            lines.append('%s %s' % (cmd_name, arg_line))

        # Create lines
        for group in cmd_options.values():
            short_line = []
            long_line = []

            group.sort(key=lambda a: a.name) # Sort alphabetically
            group.sort(cmp=lambda a, b: -1 if (a.required and not b.required) else 1) # Sort by required options first
            for option in group:
                s, l = _option_usage(option)
                if s:
                    short_line.append(s)
                if l:
                    long_line.append(l)

            arg_line = _args_usage(cmdarg_defs)

            if arg_line:
                short_line.append(arg_line)
                long_line.append(arg_line)

            if short_line:
                lines.append('%s %s' % (cmd_name, ' '.join(short_line)))
            if long_line:
                lines.append('%s %s' % (cmd_name, ' '.join(long_line)))

        return '\n'.join(lines)
 
    def define_args(args=None):
        '''Defines required/optional arguments.

        The args parameter can be in the following forms:
          - (num, name): num is the number of arguments expected, and name is the name
            to be printed when program usage is being shown.
            NOTE: num can be -1 for "0 or more agruments" and -2 for "one or more arguments"
          - (arg1, arg2, arg3): Require three arguments, each with a different name.
        '''

        if len(args) == 2 and type(args[0]) in set((int, long)) and isinstance(args[1], basestring):
            cmdarg_defs['count'] = args[0]
            cmdarg_defs['args'] = [args[1]] * abs(args[0])
            return
        elif hasattr(args, '__iter__'):
            cmdarg_defs['count'] = len(args)
            cmdarg_defs['args'] = tuple(args)
            return

        raise OptionsError('Define either (count, argname) (use -1 for zero or more, -2 for one or more) or a list of argument names.')

    def define_opt(section, name, cmd_name=None, cmd_short_name=None, cmd_only=False, type=unicode, is_config_file=False, is_help=False, help=None, cmd_group='default', **kwargs):
        '''Defines an option. Should be run before init_options().
        
           Note that you may pass in one additional kwarg: default.
           If this argument is not specified, the option is required, and
           will have to be set from either a config file or the command line.
        '''

        if not isinstance(section, basestring):
            raise OptionsError('Section name %s must be a string, not a %s' % (section, _type(section)))

        if not isinstance(name, basestring):
            raise OptionsError('Option name %s must be a string, not a %s' % (name, _type(name)))

        if cmd_name and not isinstance(cmd_name, basestring):
            raise OptionsError('cmd_name %s must be a string, not a %s' % (cmd_name, _type(cmd_name)))

        if cmd_short_name and not isinstance(cmd_short_name, basestring):
            raise OptionsError('cmd_short_name %s must be a string, not a %s' % (cmd_short_name, _type(cmd_short_name)))

        section = section.lower().strip()
        name = name.lower().strip()
        if cmd_name:
            cmd_name = cmd_name.lower().strip()

        if not re.match('^[a-z_]+[a-z0-9_]*$', section):
            raise OptionsError('%s is not a valid section name. It must contain only letters, numbers and underscores.' % section)
        
        if not re.match('^[a-z_]+[a-z0-9_]*$', name):
            raise OptionsError('%s is not a valid name. It must contain only letters, numbers and underscores.' % name)

        if cmd_name and not re.match('^[a-z0-9]+[a-z0-9-]*$', cmd_name):
            raise OptionsError('%s is not a valid cmd_name. It must contain only letters, numbers and dashes.' % cmd_short_name)

        if cmd_short_name and (len(cmd_short_name) != 1 or not re.match('^[a-zA-Z0-9]{1}$', cmd_short_name)):
            raise OptionsError('%s is not a valid cmd_short_name. It must contain only letters or numbers and be of length 1.' % cmd_short_name)

        if not hasattr(options, section):
            setattr(options, section, OptionObject())
            option_definitions[section] = {}

        if name in option_definitions[section]:
            raise OptionsError('Option %s.%s is already defined.' % (section, name))

        if cmd_only and not (cmd_name or cmd_short_name):
            raise OptionsError('Option %s.%s is defined as cmd_only, but neither cmd_name nor cmd_short_name are set.' % (section, name))

        if is_config_file and not isinstance(type(), basestring):
            raise OptionsError('Option %s.%s is defined as is_config_file, but with %s instead of %s.' % (section, name, type, unicode))

        if is_config_file and config_file_def['section']:
            raise OptionsError('Duplicate is_config_file options %s.%s and %s.%s.' % (section, name, config_file_def['section'], config_file_def['name']))

        if is_config_file and not (cmd_name or cmd_short_name):
            raise OptionsError('Option %s.%s is defined as is_config_file, but cmd_name and cmd_short_name are not specified.' % (section, name))

        if is_help and not isinstance(type(), bool):
            raise OptionsError('Option %s.%s is defined as is_help, but with %s instead of %s.' % (section, name, type, bool))

        option_definitions[section][name] = OptionObject(
            section=section,
            name=name,
            cmd_name=cmd_name,
            cmd_short_name=cmd_short_name,
            required=False,
            type=type,
            is_config_file=is_config_file,
            is_help=is_help,
            cmd_group=cmd_group,
            cmd_only=cmd_only or is_config_file or is_help,
            set_by=None,
        )

        if 'default' in kwargs:
            option_definitions[section][name].default = kwargs['default']
        elif type == bool:
            option_definitions[section][name].default = False
        else:
            option_definitions[section][name].required = True
            

        if is_config_file:
            config_file_def['section'] = section
            config_file_def['optname'] = name

    def parse_config(config_file=None):
        '''Parses a configuration file.
        
        This function sets option values if not already set by the parse_args() function.'''

        if not config_file:
            if not config_file_def['filename']:
                raise OptionsError('parse_config() needs to have an config file specified or have a command line defined as is_config_file=True')
            config_file = config_file_def['filename']

        config_file = os.path.abspath(config_file)
        if not os.path.exists(config_file):
            raise OptionsError('Configuration file %s does not exist.' % config_file)

        cp.read(config_file)

        for section in option_definitions:
            if cp.has_section(section):
                for name in option_definitions[section]:
                    if option_definitions[section][name].set_by is not None:
                        continue

                    if option_definitions[section][name].cmd_only:
                        continue

                    if name in option_definitions[section]:
                        opt = option_definitions[section][name]

                        try:
                            if opt.type in adapters:
                                setattr(getattr(options, section), name, adapters[opt.type](section, name))
                            else:
                                value = cp.get(section, name)
                                setattr(getattr(options, section), name, opt.type(value))
                        except ValueError:
                            raise OptionsUserError('Could not parse configuration file %s: section %s option %s must be of type %s' % (config_file, section, name, opt.type.__name__))
                        except NoOptionError:
                            if option_definitions[section][name].set_by or hasattr(option_definitions[section][name], 'default'):
                                continue
                            raise OptionsUserError('Could not parse configuration file %s: section %s option %s was not found' % (config_file, section, name))
                        option_definitions[section][name].set_by = parse_config

    def parse_args(argv):
        '''Parses command line arguments and sets option values as well as the cmdargs list.'''

        short_args = []
        long_args = []
        cmd_options = {}

        for section in option_definitions:
            for name, opt in option_definitions[section].iteritems():
                if not opt.cmd_name and not opt.cmd_short_name:
                    continue

                if opt.cmd_name:
                    if opt.type == bool:
                        long_args.append(opt.cmd_name)
                    else:
                        long_args.append('%s=' % opt.cmd_name)
                    cmd_options['--%s' % opt.cmd_name] = opt

                if opt.cmd_short_name:
                    if opt.type == bool:
                        short_args.append(opt.cmd_short_name)
                    else:
                        short_args.append('%s:' % opt.cmd_short_name)
                    cmd_options['-%s' % opt.cmd_short_name] = opt

        try:
            opts, args = getopt.getopt(argv, ''.join(short_args), long_args)
        except getopt.GetoptError, err:
            raise OptionsUserError(err)

        # Empty a non-local scope list, in case parse_args is called twice
        if len(cmdargs) > 0:
            [cmdargs.pop() for _ in xrange(len(cmdargs))]
        
        for arg in args:
            cmdargs.append(arg)

        for key, val in opts:
            if key in cmd_options:
                opt = cmd_options[key]
                if opt.is_help:
                    print_func(usage())
                    sys.exit(0)

                if opt.type == bool:
                    setattr(getattr(options, opt.section), opt.name, True)
                else:
                    try:
                        setattr(getattr(options, opt.section), opt.name, opt.type(val))
                    except ValueError:
                        raise OptionsUserError('Could not parse command line option %s: it must be of type %s.' % (opt.name, opt.type.__name__))
                option_definitions[opt.section][opt.name].set_by = parse_args
            else:
                raise OptionsUserError('Unknown command line parameter %s.' % key)

        if config_file_def['section'] and hasattr(getattr(options, config_file_def['section']), config_file_def['optname']):
            config_file_def['filename'] = getattr(getattr(options, config_file_def['section']), config_file_def['optname'])

    def init_options(argv=None, config_file=None):
        """Shortcut method for initializing all the options.

        Uses no configuration file unless a command line option has been defined 
        as is_config_file=True.
        """
        
        if argv is None:
            argv = sys.argv[1:]

        try:
            parse_args(argv)
            if config_file or config_file_def['filename']:
                parse_config(config_file)

            set_defaults()
            verify_all_options()

        except OptionsUserError, e:
            print_func(e)
            print_func('')
            print_func(usage())
            sys.exit(os.EX_USAGE)

    def set_defaults():
        '''Sets the default option values if they have not already been specified.'''

        for section in option_definitions:
            for name, opt in option_definitions[section].iteritems():
                if not hasattr(option_definitions[section][name], 'default'):
                    continue

                if option_definitions[section][name].set_by is not None:
                    continue

                default = getattr(option_definitions[section][name], 'default')
                setattr(getattr(options, section), name, default)

    def verify_all_options():
        '''Raises an error if required options have not been specified by the user.'''

        if config_file_def['section'] and not config_file_def['filename']:
            option = option_definitions[config_file_def['section']][config_file_def['optname']]
            if option.cmd_name:
                error = 'Required command line option --%s was not specified.' % (option.cmd_name, )
            elif option.cmd_short_name:
                error = 'Required command line option -%s was not specified.' % (option.cmd_short_name, )
            raise OptionsUserError(error)

        errors = []
        for section in option_definitions:
            for name, opt in option_definitions[section].iteritems():
                if option_definitions[section][name].required:
                    if not hasattr(getattr(options, section), name):

                        if not option_definitions[section][name].cmd_only:
                            final_words = ', and %s.%s could not be found in the config file.' % (section, name)
                        else:
                            final_words = '.'

                        if option_definitions[section][name].cmd_name:
                            error = 'Required command line option --%s was not specified%s' % (option_definitions[section][name].cmd_name, final_words)
                        elif option_definitions[section][name].cmd_short_name:
                            error = 'Required command line option -%s was not specified%s' % (option_definitions[section][name].cmd_short_name, final_words)
                        else:
                            error = 'Required option %s.%s was not specified in the config file.' % (section, name,)

                        errors.append(error)

        if cmdarg_defs['count'] == -1:
            pass # zero args required
        elif cmdarg_defs['count'] == -2:
            if len(cmdargs) < 1:
                errors.append('At least one <%s> argument required.' % cmdarg_defs['args'])
        elif cmdarg_defs['args'] is not None:
            if len(cmdargs) != cmdarg_defs['count']:
                errors.append('Required arguments were not specified: %s.' % ' '.join(map(lambda s: '<%s>' % s, cmdarg_defs['args'])))

        if len(errors) > 0:
            raise OptionsUserError('\n'.join(errors))

    return options, cmdargs, define_opt, define_args, parse_config, parse_args, set_defaults, verify_all_options, init_options, generate_sample_config, usage

options, cmdargs, define_opt, define_args, parse_config, parse_args, set_defaults, verify_all_options, init_options, generate_sample_config, usage = OptionsMeta()

__all__ = ('options', 'cmdargs', 'define_opt', 'define_args', 'parse_config', 'parse_args', 'set_defaults', 'init_options', 'verify_all_options', 'generate_sample_config', 'usage', 'OptionsError', 'OptionsUserError', 'OptionsMeta',)

__version__ = '0.1.7'

if __name__ == '__main__':
    import unittest, tempfile

    class Test(unittest.TestCase):

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
            filename = tempfile.mkstemp()[1]
            try:
                cp = SafeConfigParser()
                cp.add_section('sec')
                cp.set('sec', 'foo', 'foo')
                cp.set('sec', 'bar', '-1')
                cp.set('sec', 'baz', '-0.1')
                cp.set('sec', 'hum', 'yes')
                cp.set('sec', 'dum', 'no')

                cp.write(open(filename, 'wb'))

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
            self.define_opt('sec', 'foo', default='foo')
            self.define_opt('sec', 'bar', type=int, default=-1)
            self.define_opt('sec', 'baz', type=float, default=-0.1)
            self.define_opt('sec', 'hum', type=bool, default=True)
            self.define_opt('sec', 'dum', type=bool, default=False)
            self.define_opt('sec', 'nop', type=unicode)

            self.set_defaults()

            self.assertEqual(self.options.sec.foo, 'foo')
            self.assertEqual(self.options.sec.bar, -1)
            self.assertAlmostEqual(self.options.sec.baz, -0.1)
            self.assertEqual(self.options.sec.hum, True)
            self.assertEqual(self.options.sec.dum, False)
            self.assertTrue(not hasattr(self.options.sec, 'nop'))

        def test_init_options(self):
            filename = tempfile.mkstemp()[1]
            try:

                conf = '''
                    [sec]
                    foo = conf-foo
                    nop = conf-nop
                    
                    [con]
                    foo = conf-foo
                    bar = -2
                    baz = -0.2
                    hum = False
                    dum = True
                    nop = conf-nop
                    
                    [cmd]
                    foo = conf-foo
                '''
                
                open(filename, 'wb').write('\n'.join(map(lambda s: s.strip(), conf.split('\n'))))

                self.define_opt('sec', 'foo', default='foo')
                self.define_opt('sec', 'bar', type=int, default=-1)
                self.define_opt('sec', 'baz', type=float, default=-0.1)
                self.define_opt('sec', 'hum', type=bool, default=True)
                self.define_opt('sec', 'dum', type=bool, default=False)
                self.define_opt('sec', 'nop', type=unicode)

                self.define_opt('con', 'foo', default='foo')
                self.define_opt('con', 'bar', type=int, default=-1)
                self.define_opt('con', 'baz', type=float, default=-0.1)
                self.define_opt('con', 'hum', type=bool, default=True)
                self.define_opt('con', 'dum', type=bool, default=False)
                self.define_opt('con', 'nop', type=unicode)

                self.define_opt('cmd', 'config', cmd_name='config', cmd_short_name='c', is_config_file=True)
                self.define_opt('cmd', 'help', type=bool, cmd_name='help', cmd_short_name='h', is_help=True, cmd_group='help')

                self.define_opt('cmd', 'foo', default='foo', cmd_name='foo', cmd_short_name='f')
                self.define_opt('cmd', 'bar', type=int, default=-1, cmd_name='bar')
                self.define_opt('cmd', 'baz', type=float, default=-0.1, cmd_short_name='z')
                self.define_opt('cmd', 'hum', type=bool, default=True, cmd_name='hum')
                self.define_opt('cmd', 'dum', type=bool, default=False, cmd_short_name='d')
                self.define_opt('cmd', 'nop', type=unicode, cmd_name='nop')

                self.assertRaises(SystemExit, self.init_options, ['--help'])
                self.assertRaises(SystemExit, self.init_options, [])
                self.assertRaises(SystemExit, self.init_options, ['--config=%s' % filename])
                self.init_options(['--config=%s' % filename, '--nop=cmd-nop', '--bar=-15', '-z', '-0.3', '--hum', '-d'])

                self.assertEqual(self.options.sec.foo, 'conf-foo')
                self.assertEqual(self.options.sec.bar, -1)
                self.assertAlmostEqual(self.options.sec.baz, -0.1)
                self.assertEqual(self.options.sec.hum, True)
                self.assertEqual(self.options.sec.dum, False)
                self.assertEqual(self.options.sec.nop, 'conf-nop')

                self.assertEqual(self.options.con.foo, 'conf-foo')
                self.assertEqual(self.options.con.bar, -2)
                self.assertAlmostEqual(self.options.con.baz, -0.2)
                self.assertEqual(self.options.con.hum, False)
                self.assertEqual(self.options.con.dum, True)
                self.assertEqual(self.options.con.nop, 'conf-nop')

                self.assertEqual(self.options.cmd.foo, 'conf-foo')
                self.assertEqual(self.options.cmd.bar, -15)
                self.assertAlmostEqual(self.options.cmd.baz, -0.3)
                self.assertEqual(self.options.cmd.hum, True)
                self.assertEqual(self.options.cmd.dum, True)
                self.assertEqual(self.options.cmd.nop, 'cmd-nop')

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

                open(filename, 'wb').write(self.generate_sample_config())

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

    unittest.main()
