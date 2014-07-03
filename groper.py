
from __future__ import unicode_literals, print_function

try:
    from configparser import RawConfigParser, NoOptionError
except ImportError:
    from ConfigParser import RawConfigParser, NoOptionError

from io import StringIO

import getopt, os.path, sys, re, codecs

class OptionObject(object):
    def __init__(self, **kwargs):
        for key, val in kwargs.items():
            setattr(self, key, val)

class OptionsError(Exception): pass
class OptionsUserError(Exception): pass

def OptionsMeta(print_func=None):
    '''Creates a private scope for the options manupulation functions and returns them.

    This function us used to create a module-wide global options object and its 
    manipulation functions. It may be used to generate local options objects, for 
    example for unit testing.
    '''

    print_func = print_func or print # Pass in a custom print function to use, e.g. stderr

    option_definitions = {}
    cp = RawConfigParser()
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

    try:
        _basestring = basestring
    except NameError:
        _basestring = str

    try:
        _long = long
    except NameError:
        _long = int

    def generate_sample_config():
        '''Returns a string containing a sample configuration file based on the defined options.'''
        
        f = StringIO()
        try:
            for section in option_definitions:
                f.write('[{0}]\n'.format(section))

                for name, opt in option_definitions[section].items():
                    if opt.cmd_only:
                        continue

                    opt_name = name if hasattr(opt, 'default') else '#{0}'.format(name)
                    opt_val = '{0}'.format(opt.default) if hasattr(opt, 'default') else '<{0}>'.format(name.upper())
                    
                    f.write('{0} = {1}\n'.format(opt_name, opt_val))

                f.write("\n")

            return f.getvalue()
        finally:
            f.close()
        
    def _option_usage(option):
        '''Create an option usage line part based on option definition.
        
            Returns a tuple of (short_str, long_str) to be added.
        '''
        s, l = None, None

        wrap_optional = lambda option, s: s if option.required else ('[{0}]'.format(s))

        if option.cmd_short_name:
            if option.type != bool:
                s = wrap_optional(option, '-{0} <{1}>'.format(option.cmd_short_name, option.cmd_name or option.name))
            else:
                s = wrap_optional(option, '-{0}'.format(option.cmd_short_name))
        elif option.cmd_name and option.required:
            if option.type != bool:
                s = wrap_optional(option, '--{0}=<{1}>'.format(option.cmd_name, option.cmd_name or option.name))
            else:
                s = wrap_optional(option, '--{0}'.format(option.cmd_name))
       
        
        if option.cmd_name:
            if option.type != bool:
                l = wrap_optional(option, '--{0}=<{1}>'.format(option.cmd_name, option.cmd_name or option.name))
            else:
                l = wrap_optional(option, '--{0}'.format(option.cmd_name))
        elif option.cmd_short_name and option.required:
            if option.type != bool:
                l = wrap_optional(option, '-{0} <{1}>'.format((option.cmd_short_name, option.cmd_name or option.name)))
            else:
                l = wrap_optional(option, '-{0}'.format(option.cmd_short_name))

        return s, l

    def _args_usage(cmdargs_def):
        if cmdarg_defs['count'] == -1:
            return '[{0}] ...'.format(cmdarg_defs['args'][0])
        elif cmdarg_defs['count'] == -2:
            return '<{0}> [{1}] ...'.format(cmdarg_defs['args'][0], cmdarg_defs['args'][0])
        elif cmdarg_defs['args']:
            return ' '.join(['<{0}>'.format(s) for s in cmdarg_defs['args']])

    def usage(cmd_name=None):
        '''Returns usage/help string based on defined options.'''

        cmd_name = cmd_name or os.path.basename(sys.argv[0])
        
        lines = ['Usage:', '',]

        # Group all options
        cmd_options = {}
        for section in option_definitions:
            for name, opt in option_definitions[section].items():
                if opt.cmd_name or opt.cmd_short_name:
                    if opt.cmd_group not in cmd_options:
                        cmd_options[opt.cmd_group] = []
                    cmd_options[opt.cmd_group].append(opt)

        if not cmd_options and cmdarg_defs['count']:
            arg_line = _args_usage(cmdarg_defs)
            lines.append('{0} {1}'.format(cmd_name, arg_line))

        # Create lines
        for group in cmd_options.values():
            short_line = []
            long_line = []

            group.sort(key=lambda a: a.name) # Sort alphabetically
            group.sort(key=lambda a: int(a.required)) # Sort by required options first
            
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
                lines.append('{0} {1}'.format(cmd_name, ' '.join(short_line)))
            if long_line:
                lines.append('{0} {1}'.format(cmd_name, ' '.join(long_line)))

        return '\n'.join(lines)
 
    def define_args(args=None):
        '''Defines required/optional arguments.

        The args parameter can be in the following forms:
          - (num, name): num is the number of arguments expected, and name is the name
            to be printed when program usage is being shown.
            NOTE: num can be -1 for "0 or more agruments" and -2 for "one or more arguments"
          - (arg1, arg2, arg3): Require three arguments, each with a different name.
        '''

        if len(args) == 2 and type(args[0]) in set((int, _long)) and isinstance(args[1], _basestring):
            cmdarg_defs['count'] = args[0]
            cmdarg_defs['args'] = [args[1]] * abs(args[0])
            return
        elif hasattr(args, '__iter__'):
            cmdarg_defs['count'] = len(args)
            cmdarg_defs['args'] = tuple(args)
            return

        raise OptionsError('Define either (count, argname) (use -1 for zero or more, -2 for one or more) or a list of argument names.')

    def define_opt(section, name, cmd_name=None, cmd_short_name=None, cmd_only=False, type=_type(''), is_config_file=False, is_help=False, help=None, cmd_group='default', **kwargs):
        '''Defines an option. Should be run before init_options().
        
           Note that you may pass in one additional kwarg: default.
           If this argument is not specified, the option is required, and
           will have to be set from either a config file or the command line.
        '''

        if not isinstance(section, _basestring):
            raise OptionsError('Section name {0} must be a string, not a {1}'.format(section, _type(section)))

        if not isinstance(name, _basestring):
            raise OptionsError('Option name {0} must be a string, not a {1}'.format(name, _type(name)))

        if cmd_name and not isinstance(cmd_name, _basestring):
            raise OptionsError('cmd_name {0} must be a string, not a {1}'.format(cmd_name, _type(cmd_name)))

        if cmd_short_name and not isinstance(cmd_short_name, _basestring):
            raise OptionsError('cmd_short_name {0} must be a string, not a {1}'.format(cmd_short_name, _type(cmd_short_name)))

        section = section.lower().strip()
        name = name.lower().strip()
        if cmd_name:
            cmd_name = cmd_name.lower().strip()

        if not re.match('^[a-z_]+[a-z0-9_]*$', section):
            raise OptionsError('{0} is not a valid section name. It must contain only letters, numbers and underscores.'.format(section))
        
        if not re.match('^[a-z_]+[a-z0-9_]*$', name):
            raise OptionsError('{0} is not a valid name. It must contain only letters, numbers and underscores.'.format(name))

        if cmd_name and not re.match('^[a-z0-9]+[a-z0-9-]*$', cmd_name):
            raise OptionsError('{0} is not a valid cmd_name. It must contain only letters, numbers and dashes.'.format(cmd_short_name))

        if cmd_short_name and (len(cmd_short_name) != 1 or not re.match('^[a-zA-Z0-9]{1}$', cmd_short_name)):
            raise OptionsError('{0} is not a valid cmd_short_name. It must contain only letters or numbers and be of length 1.'.format(cmd_short_name))

        if not hasattr(options, section):
            setattr(options, section, OptionObject())
            option_definitions[section] = {}

        if name in option_definitions[section]:
            raise OptionsError('Option {0}.{1} is already defined.'.format(section, name))

        if cmd_only and not (cmd_name or cmd_short_name):
            raise OptionsError('Option {0}.{1} is defined as cmd_only, but neither cmd_name nor cmd_short_name are set.'.format(section, name))

        if is_config_file and not isinstance(type(), _basestring):
            raise OptionsError('Option {0}.{1} is defined as is_config_file, but with {2} instead of {3}.'.format(section, name, type, _type('')))

        if is_config_file and config_file_def['section']:
            raise OptionsError('Duplicate is_config_file options {0}.{1} and {2}.{3}.'.format(section, name, config_file_def['section'], config_file_def['name']))

        if is_config_file and not (cmd_name or cmd_short_name):
            raise OptionsError('Option {0}.{1} is defined as is_config_file, but cmd_name and cmd_short_name are not specified.'.format(section, name))

        if is_help and not isinstance(type(), bool):
            raise OptionsError('Option {0}.{1} is defined as is_help, but with {2} instead of {3}.'.format(section, name, type, bool))

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
            
            if 'default' in kwargs:
                config_file_def['filename'] = kwargs['default']

    def parse_config(config_file=None):
        '''Parses a configuration file.
        
        This function sets option values if not already set by the parse_args() function.'''

        if not config_file:
            if not config_file_def['filename']:
                raise OptionsError('You must pass a config_file path to parse_config() or define a command line option is_config_file=True with an optional default.')
            config_file = config_file_def['filename']

        config_file = os.path.abspath(config_file)
        if not os.path.exists(config_file):
            raise OptionsUserError('Configuration file {0} does not exist.'.format(config_file))

        cp.readfp(codecs.open(config_file, 'r', 'utf-8'))

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
                        except ValueError as e:
                            print(e)
                            raise OptionsUserError('Could not parse configuration file {0}: section {1} option {2} must be of type {3}, not {4}'.format(config_file, section, name, opt.type.__name__, type(getattr(getattr(options, section), name))))
                        except NoOptionError:
                            if option_definitions[section][name].set_by or hasattr(option_definitions[section][name], 'default'):
                                continue
                            raise OptionsUserError('Could not parse configuration file {0}: section {1} option {2} was not found'.format(config_file, section, name))
                        option_definitions[section][name].set_by = parse_config

    def parse_args(argv):
        '''Parses command line arguments and sets option values as well as the cmdargs list.'''

        short_args = []
        long_args = []
        cmd_options = {}

        for section in option_definitions:
            for name, opt in option_definitions[section].items():
                if not opt.cmd_name and not opt.cmd_short_name:
                    continue

                if opt.cmd_name:
                    if opt.type == bool:
                        long_args.append(opt.cmd_name)
                    else:
                        long_args.append('{0}='.format(opt.cmd_name))
                    cmd_options['--{0}'.format(opt.cmd_name)] = opt

                if opt.cmd_short_name:
                    if opt.type == bool:
                        short_args.append(opt.cmd_short_name)
                    else:
                        short_args.append('{0}:'.format(opt.cmd_short_name))
                    cmd_options['-{0}'.format(opt.cmd_short_name)] = opt

        try:
            opts, args = getopt.getopt(argv, ''.join(short_args), long_args)
        except getopt.GetoptError as err:
            raise OptionsUserError(err)

        # Empty a non-local scope list, in case parse_args is called twice
        if len(cmdargs) > 0:
            [cmdargs.pop() for _ in range(len(cmdargs))]
        
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
                        raise OptionsUserError('Could not parse command line option {0}: it must be of type {1}.'.format(opt.name, opt.type.__name__))
                option_definitions[opt.section][opt.name].set_by = parse_args
            else:
                raise OptionsUserError('Unknown command line parameter {0}.'.format(key))

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

        except OptionsUserError as e:
            print_func(e)
            print_func('')
            print_func(usage())
            sys.exit(os.EX_USAGE)

    def set_defaults():
        '''Sets the default option values if they have not already been specified.'''

        for section in option_definitions:
            for name, opt in option_definitions[section].items():
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
                error = 'Required command line option --{0} was not specified.'.format(option.cmd_name)
            elif option.cmd_short_name:
                error = 'Required command line option -{0} was not specified.'.format(option.cmd_short_name)
            raise OptionsUserError(error)

        errors = []
        for section in option_definitions:
            for name, opt in option_definitions[section].items():
                if option_definitions[section][name].required:
                    if not hasattr(getattr(options, section), name):

                        if not option_definitions[section][name].cmd_only:
                            final_words = ', and {0}.{1} could not be found in the config file.'.format(section, name)
                        else:
                            final_words = '.'

                        if option_definitions[section][name].cmd_name:
                            error = 'Required command line option --{0} was not specified{1}'.format(option_definitions[section][name].cmd_name, final_words)
                        elif option_definitions[section][name].cmd_short_name:
                            error = 'Required command line option -{0} was not specified{1}'.format(option_definitions[section][name].cmd_short_name, final_words)
                        else:
                            error = 'Required option {0}.{1} was not specified in the config file.'.format(section, name,)

                        errors.append(error)

        if cmdarg_defs['count'] == -1:
            pass # zero args required
        elif cmdarg_defs['count'] == -2:
            if len(cmdargs) < 1:
                errors.append('At least one <{0}> argument required.'.format(cmdarg_defs['args']))
        elif cmdarg_defs['args'] is not None:
            if len(cmdargs) != cmdarg_defs['count']:
                errors.append('Required arguments were not specified: {0}.'.format(' '.join(['<{0}>'.format(s) for s in cmdarg_defs['args']])))

        if len(errors) > 0:
            raise OptionsUserError('\n'.join(errors))

    return options, cmdargs, define_opt, define_args, parse_config, parse_args, set_defaults, verify_all_options, init_options, generate_sample_config, usage

options, cmdargs, define_opt, define_args, parse_config, parse_args, set_defaults, verify_all_options, init_options, generate_sample_config, usage = OptionsMeta()

__all__ = ('options', 'cmdargs', 'define_opt', 'define_args', 'parse_config', 'parse_args', 'set_defaults', 'init_options', 'verify_all_options', 'generate_sample_config', 'usage', 'OptionsError', 'OptionsUserError', 'OptionsMeta',)

__version__ = '0.3.1'

