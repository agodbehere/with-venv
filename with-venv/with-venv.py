# -*- coding: utf-8 -*-
"""
Run scripts in a clean virtual environment.

Useful for testing, building, and deploying.

:author: Andrew B Godbehere
:date: 4/21/16
"""

import venv
import sys
import os
from urllib.parse import urlparse
from urllib.request import urlretrieve
from threading import Thread
from subprocess import Popen, PIPE
import os.path
import types


class ExtendedEnvBuilder(venv.EnvBuilder):
    """
    This builder installs setuptools and pip so that you can pip or
    easy_install other packages into the created environment.

    Note: This class is from stdlib docs, with some minor modifications.

    :param nodist: If True, setuptools and pip are not installed into the
                   created environment.
    :param nopip: If True, pip is not installed into the created
                  environment.
    :param progress: If setuptools or pip are installed, the progress of the
                     installation can be monitored by passing a progress
                     callable. If specified, it is called with two
                     arguments: a string indicating some progress, and a
                     context indicating where the string is coming from.
                     The context argument can have one of three values:
                     'main', indicating that it is called from virtualize()
                     itself, and 'stdout' and 'stderr', which are obtained
                     by reading lines from the output streams of a subprocess
                     which is used to install the app.

                     If a callable is not specified, default progress
                     information is output to sys.stderr.
    """

    def __init__(self, *args, **kwargs):
        self.nodist = kwargs.pop('nodist', False)
        self.nopip = kwargs.pop('nopip', False)
        self.progress = kwargs.pop('progress', None)
        self.verbose = kwargs.pop('verbose', False)
        self.context = None
        super().__init__(*args, **kwargs)

    def create(self, env_dir):
        super().create(env_dir)
        return clean_env(self.context)   # TODO: Get a better handle on self.context

    def post_setup(self, context):
        """
        Set up any packages which need to be pre-installed into the
        environment being created.

        :param context: The information for the environment creation request
                        being processed.
        """
        self.context = context
        #os.environ['VIRTUAL_ENV'] = context.env_dir
        #if not self.nodist:
        #    self.install_setuptools(context)
        # Can't install pip without setuptools
        #if not self.nopip and not self.nodist:
        #    self.install_pip(context)
    '''
    def ensure_directories(self, env_dir):
        context = super().ensure_directories(env_dir)
        print("ORIGINAL CONTEXT: ")
        for k, v in iter(context.__dict__.items()):
            print("{}: {}".format(k, v))
        return context
    '''

    def ensure_directories(self, env_dir):
        """
        Create the directories for the environment.

        Note: Minor modifications made to original method from venv.

        Returns a context object which holds paths in the environment,
        for use by subsequent logic.
        """

        def create_if_needed(d):
            if not os.path.exists(d):
                os.makedirs(d)
            elif os.path.islink(d) or os.path.isfile(d):
                raise ValueError('Unable to create directory %r' % d)

        if os.path.exists(env_dir) and self.clear:
            self.clear_directory(env_dir)
        context = types.SimpleNamespace()
        context.env_dir = env_dir
        context.env_name = os.path.split(env_dir)[1]
        context.prompt = '(%s) ' % context.env_name
        create_if_needed(env_dir)
        env = os.environ

        # TODO: CHANGE EXECUTABLE WHEN RUNNING FROM WITHIN A VIRTUALENV
        if 'VIRTUAL_ENV' in os.environ:
            vpath = os.environ['VIRTUAL_ENV']
            # print("VPATH: {}".format(vpath))
            base_binpath = os.pathsep.join(
                [x for x in os.environ['PATH'].split(os.pathsep) if not x.startswith(vpath)]
            )
            # print("BASEPATH: {}".format(base_binpath))
            executable = None
            for p in base_binpath.split(os.pathsep):
                # exepath = os.path.join(p, "python3.5")
                exepath = os.path.join(p, "python3")
                # print("LOOKING FOR {}".format(exepath))
                if os.path.exists(exepath):
                    # print("UPDATING EXECUTABLE: {}".format(exepath))
                    executable = exepath
                    # self.context.env_exe = exepath # TODO: REMAKE SYMLINK
                    break
            if not executable:
                raise RuntimeError("No valid python executable discovered.")
        else:
            if sys.platform == 'darwin' and '__PYVENV_LAUNCHER__' in env:
                executable = os.environ['__PYVENV_LAUNCHER__']
            else:
                executable = sys.executable

        dirname, exename = os.path.split(os.path.abspath(executable))
        context.executable = executable
        context.python_dir = dirname
        context.python_exe = exename
        if sys.platform == 'win32':
            binname = 'Scripts'
            incpath = 'Include'
            libpath = os.path.join(env_dir, 'Lib', 'site-packages')
        else:
            binname = 'bin'
            incpath = 'include'
            libpath = os.path.join(env_dir, 'lib',
                                   'python%d.%d' % sys.version_info[:2],
                                   'site-packages')
        context.inc_path = path = os.path.join(env_dir, incpath)
        create_if_needed(path)
        create_if_needed(libpath)
        # Issue 21197: create lib64 as a symlink to lib on 64-bit non-OS X POSIX
        if ((sys.maxsize > 2 ** 32) and (os.name == 'posix') and
                (sys.platform != 'darwin')):
            link_path = os.path.join(env_dir, 'lib64')
            if not os.path.exists(link_path):  # Issue #21643
                os.symlink('lib', link_path)
        context.bin_path = binpath = os.path.join(env_dir, binname)
        context.bin_name = binname
        context.env_exe = os.path.join(binpath, exename)
        create_if_needed(binpath)
        return context


class clean_env:
    """
    Manage a clean environment.
    """

    def __init__(self, context):
        self.context = context

    def reader(self, stream):
        """
        Read lines from a subprocess' output stream and either pass to a progress
        callable (if specified) or write progress information to sys.stderr.
        """
        while True:
            s = stream.readline()
            if not s:
                break

            # if not self.verbose:
            #    sys.stderr.write('.')
            # else:
            sys.stderr.write(s.decode('utf-8'))
            sys.stderr.flush()
            #sys.stderr.write('.')

        stream.close()

    def install_script(self, name, url):

        _, _, path, _, _, _ = urlparse(url)
        fn = os.path.split(path)[-1]
        binpath = self.context.bin_path
        print("BINPATH: {}".format(binpath))
        distpath = os.path.join(binpath, fn)
        print("DISTPATH: {}".format(distpath))
        # Download script into the env's binaries folder
        urlretrieve(url, distpath)

        term = ''
        sys.stderr.write('Installing %s ...%s' % (name, term))
        sys.stderr.flush()

        # Install in the env
        args = [self.context.env_exe, fn]

        print("ENV_EXE: {}".format(self.context.env_exe))
        print("PYTHON_EXE: {}".format(self.context.python_exe))
        #args = ['python', fn]
        #print("args: {}".format(args))
        p = Popen(args, stdout=PIPE, stderr=PIPE, cwd=binpath, env=self.new_environ, start_new_session=True)
        t1 = Thread(target=self.reader, args=(p.stdout,))
        t1.start()
        t2 = Thread(target=self.reader, args=(p.stderr,))
        t2.start()
        p.wait()
        t1.join()
        t2.join()

        sys.stderr.write('done.\n')
        # Clean up - no longer needed
        os.unlink(distpath)

    def run_in_env(self, script):
        #for k, v in iter(self.new_environ.items()):
        #    print("{}: {}".format(k, v))
        #print("RUNNING {} using {}".format(script, self.context.env_exe))
        #print("args: {}".format([self.context.env_exe, script]))
        p = Popen([self.context.python_exe, script], stdout=PIPE, stderr=PIPE, env=self.new_environ, cwd='.',
                  start_new_session=True)
        t1 = Thread(target=self.reader, args=(p.stdout,))
        t1.start()
        t2 = Thread(target=self.reader, args=(p.stderr,))
        t2.start()
        p.wait()
        t1.join()
        t2.join()

    def __enter__(self):
        # activate

        if 'VIRTUAL_ENV' in os.environ:
            vpath = os.environ['VIRTUAL_ENV']
            #print("VPATH: {}".format(vpath))
            base_binpath = os.pathsep.join([x for x in os.environ['PATH'].split(os.pathsep) if not x.startswith(vpath)])
            #print("BASEPATH: {}".format(base_binpath))

        else:
            base_binpath = os.environ['PATH']

        self.new_environ = dict(os.environ)
        self.new_environ['VIRTUAL_ENV'] = self.context.env_dir
        self.new_environ['PATH'] = self.context.bin_path + os.pathsep + base_binpath
        if "PYTHONHOME" in self.new_environ:
            print("HAS PYTHONHOME")
            self.new_environ.pop("PYTHONHOME")
        '''
        self.install_script('setuptools', 'https://bitbucket.org/pypa/setuptools/downloads/ez_setup.py')

        # clear up the setuptools archive which gets downloaded
        def pred(o):
            return o.startswith('setuptools-') and o.endswith('.tar.gz')
        # pred = lambda o: o.startswith('setuptools-') and o.endswith('.tar.gz')
        files = filter(pred, os.listdir(self.context.bin_path))
        for f in files:
            f = os.path.join(self.context.bin_path, f)
            os.unlink(f)
        '''
        self.install_script('pip', 'https://bootstrap.pypa.io/get-pip.py')
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # TODO: Remove the virtual environment.
        pass


if __name__ == "__main__":
    env = ExtendedEnvBuilder()
    # Note: Will always create a clean copy of current python environment. Relies on other tools, build systems, to iterate over multiple python executables.
    with env.create('foo') as fooenv:
        for k, v in iter(fooenv.context.__dict__.items()):
            print("{}: {}".format(k, v))
        fooenv.run_in_env('test_articulation.py')
    # os.environ['VIRTUAL_ENV'] = env.context.env_dir
