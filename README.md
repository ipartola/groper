## groper: simple Python command line and config file options

Python programs that run from the command line often times contain code that looks like this:

    DEFAULT_PORT = 8080
    def main():
        if len(sys.argv) > 2 and sys.argv[1] == '-p':
            port = int(sys.argv[2])
        else:
            port = DEFAULT_PORT

While technically correct, this code does not scale well. The next evolution of this code would use either getopt, argparse or optparse to help abstract parsing command line options. However, at some point the number of options would grow so large that a configuration file might be warranted and ConfigParser is introduced.

However, the complexity of the code grows as this happens. To use (argparse|optparse|getopt) + ConfigParser effectively and correctly the program needs to:

*   Parse the command line args, and figure out where the configuration file resides
*   Read the configuration file and combine it with the command line args (the command line args take precidence)
*   If not all required command line args are specified, print program usage and exit.
*   The wrapper around ConfigPraser needs to provide a simple way to access the data
*   Some values need to have defaults, which should be used if the config file and the command line args do not specify one

Implementing this logic in each Python program is redundant. However, it seems that most programs do it this way. groper provides a simple unified interface for reading command line args, configuration files, setting defaults, printing program usage and even generating sample configuration files. Here is an example of its usage:


    from groper import define_opt, init_options

    define_opt('server', 'host', type=str, cmd_name='host', cmd_short_name='h', default='localhost')
    define_opt('server', 'port', type=int, cmd_name='port', cmd_short_name='p', default=8080)
    define_opt('server', 'daemon', type=bool, cmd_name='daemon', cmd_short_name='d')

    # init_options() will automatically read this file. If you don't use a config file, simply comment this out
    #define_opt('meta', 'config', type=str, cmd_only=True, cmd_name='config', cmd_short_name='c', is_config_file=True)

    # If specified: program usage will be printed and returned
    # The cmd_group param means that when the usage is printed, this option will be specified in its own group
    define_opt('meta', 'help', type=bool, cmd_only=True, cmd_name='help', cmd_short_name='H', is_help=True, cmd_group='help')

    def main():
        options = init_options()
        print(options.server.host)
        print(options.server.port)
        print(options.server.daemon)

    if __name__ == '__main__':
        main()


That's it. You can use the options object from any module in which you import it to get access to the program settings. The *default* argument to the define_opt() function also provides a great feature: you can now specify all your constants as configurable options that can be read from the configuration file.

As if that wasn't enough, you can even generate sample configuration files:


    from groper import define_opt, init_options, options

    define_opt('server', 'host', type=str, cmd_name='host', cmd_short_name='h', default='localhost')
    define_opt('server', 'port', type=int, cmd_name='port', cmd_short_name='p', default=8080)
    define_opt('server', 'daemon', type=bool, cmd_name='daemon', cmd_short_name='d')

    print generate_sample_config()


Hopefully you will find groper useful. It can be installed via PyPi:

    $ pip install groper

groper is licensed under the MIT license and is Copyright (c) 2011-2024 Igor Partola

