import unittest
import time
import datetime
import errno
import sys
from pathlib import Path
from yamlns import namespace as ns
from .execution import (
    Execution,
    executionRoot,
    removeRecursive,
    children,
)

def assertSandboxes(self, expected):
    result = [
        str(p)
        for p in sorted(executionRoot.glob('**/*'))
    ]
    self.assertEqual(result, expected)

def assertContentEqual(self, path1, path2):
    self.assertMultiLineEqual(
        path1.read_text(encoding='utf8'),
        path2.read_text(encoding='utf8'),
    )

def waitExist(self, file, miliseconds=200):
    for i in range(miliseconds):
        if file.exists():
            return True
        time.sleep(0.001)
    return False
        

class Execution_Test(unittest.TestCase):

    assertSandboxes = assertSandboxes
    assertContentEqual = assertContentEqual
    waitExist = waitExist

    def setUp(self):
        removeRecursive(executionRoot)

    def test_simpleProperties(self):
        e = Execution(name="hola")
        self.assertEqual(e.name, 'hola')
        self.assertEqual(e.path, executionRoot/'hola')
        self.assertEqual(e.outputFile, executionRoot/'hola'/'output.txt')
        self.assertEqual(e.pidFile, executionRoot/'hola'/'pid')
        self.assertEqual(e.pid, None)

    def test_createSandbox(self):
        e = Execution(name="hola")
        self.assertEqual(False, e.path.exists())
        e.createSandbox()
        self.assertEqual(True, e.path.exists())
        self.assertSandboxes([
            'executions/hola',
        ])

    def test_list_noExecutions(self):
        result = [e.name for e in Execution.list()]
        self.assertEqual(result,[
        ])

    def test_list_singleExecution(self):
        execution = Execution(name="First")
        execution.createSandbox()
        result = [e.name for e in Execution.list()]
        self.assertEqual(result,[
            "First",
        ])

    def test_list_manyExecutions(self):
        execution1 = Execution(name="First")
        execution1.createSandbox()
        time.sleep(0.01) # ensure the timestamp changes
        execution2 = Execution(name="Last")
        execution2.createSandbox()
        result = [e.name for e in Execution.list()]
        self.assertEqual(result,[
            "Last",
            "First",
        ])


    def test_run_executesCommand(self):
        execution = Execution(name="One")
        execution.createSandbox()
        execution.run([
            "python",
            "-c",
            "open('{}','w').write('hola')".format(execution.path.resolve()/'itworks'),
        ])
        self.assertEqual(self.waitExist(execution.path/'itworks',1000), True)
        self.assertEqual((execution.path/'itworks').read_text(), 'hola')

    def test_run_inSandbox(self):
        execution = Execution(name="One")
        execution.createSandbox()
        execution.run([
            "python",
            "-c",
            "open('{}','w').write('hola')".format('itworks'),
        ])
        self.waitExist(execution.path/'itworks')
        self.assertEqual((execution.path/'itworks').read_text(), 'hola')

    def test_run_generatesPidFile(self):
        execution = Execution(name="One")
        execution.createSandbox()
        execution.run([
            "python",
            "-c",
            "import os; open('mypid','w').write('{}'.format(os.getpid()))",
        ])
        self.waitExist(execution.path/'mypid')
        self.assertContentEqual(
            execution.path/'mypid',
            execution.pidFile)

    def test_run_capturesStdOut(self):
        execution = Execution(name="One")
        execution.createSandbox()
        execution.run([
            "python",
            "-c",
            "import sys;"
                "sys.stdout.write('Hola'); sys.stdout.flush();"
                "open('ended','w').write('')",
        ])
        self.waitExist(execution.path/'ended')
        self.assertEqual((execution.outputFile).read_text(), "Hola") 

    def test_run_capturesStdErr(self):
        execution = Execution(name="One")
        execution.createSandbox()
        execution.run([
            "python",
            "-c",
            "import sys;"
                "sys.stderr.write('Hola'); sys.stderr.flush();"
                "open('ended','w').write('')",
        ])
        self.waitExist(execution.path/'ended')
        self.assertEqual((execution.outputFile).read_text(), "Hola") 

    @unittest.skipIf(sys.version_info[0] < 3, "Just for Python 3 until 3.7")
    @unittest.skipIf(sys.version_info[:2] >= (3,8), "Just for Python 3 until 3.7")
    def test_run_badCommand_py37(self):
        # TODO: This should be more detectable for the listing
        execution = Execution(name="One")
        execution.createSandbox()
        with self.assertRaises(OSError) as ctx:
            execution.run([
                "badcommandthatdoesnotexist",
            ])
        self.assertEqual(format(ctx.exception),
            "[Errno 2] No such file or directory: 'badcommandthatdoesnotexist': 'badcommandthatdoesnotexist'")

    @unittest.skipIf(sys.version_info[:2] < (3,8), "Just for Python 3.8 and above")
    def test_run_badCommand_py38(self):
        # TODO: This should be more detectable for the listing
        execution = Execution(name="One")
        execution.createSandbox()
        with self.assertRaises(OSError) as ctx:
            execution.run([
                "badcommandthatdoesnotexist",
            ])
        self.assertEqual(format(ctx.exception),
            "[Errno 2] No such file or directory: 'badcommandthatdoesnotexist'")

    @unittest.skipIf(sys.version_info[0] >= 3, "Just for Python 2")
    def test_run_badCommand_py2(self):
        # TODO: This should be more detectable for the listing
        execution = Execution(name="One")
        execution.createSandbox()
        with self.assertRaises(OSError) as ctx:
            execution.run([
                "badcommandthatdoesnotexist",
            ])
        self.assertEqual(format(ctx.exception),
            "[Errno 2] No such file or directory")

    def test_pid_whenNotRunning(self):
        execution = Execution(name="One")
        execution.createSandbox()
        self.assertEqual(None, execution.pid)

    def test_pid_afterRunning(self):
        execution = Execution(name="One")
        execution.createSandbox()
        p = execution.run('ls') # This is new
        self.assertEqual(p.pid, execution.pid)

    def test_pid_onceRunningIsCached(self):
        execution = Execution(name="One")
        execution.createSandbox()
        p = execution.run('ls')
        execution.pid # this access caches
        execution.pidFile.unlink() # This is new
        self.assertEqual(p.pid, execution.pid)

    def test_stop_sendsSigInt_python(self):
        execution = Execution(name="One")
        execution.createSandbox()
        execution.run([
            "python",
            "-c",
            "import signal, time;\n"
            "from pathlib import Path;\n"
            "terminated=False;\n"
            "def stop(signal, frame):\n"
            "  global terminated\n"
            "  terminated=True\n"
            "signal.signal(signal.SIGINT, stop)\n"
            "Path('ready').touch()\n"
            "while not terminated: time.sleep(0.01)\n"
            "Path('ended').touch()\n"
            ,
        ])
        self.assertEqual(self.waitExist(execution.path/'ready',1000), True)
        self.assertEqual((execution.path/'ended').exists(), False)
        found = execution.stop()
        self.assertEqual(self.waitExist(execution.path/'ended',1000), True)
        self.assertEqual(found, True)

    def test_stop_sendsSigInt_bash(self):
        execution = Execution(name="One")
        execution.createSandbox()
        execution.run([
            "bash",
            "-c",
            "terminated=0\n"
            "function stop() {\n"
            "    touch stopping\n"
            "    terminated=1\n"
            "}\n"
            "trap 'stop' SIGINT\n"
            "touch ready\n"
            "while true; do\n"
            "  [ $terminated == 1 ] && {\n"
            "    break\n"
            "}\n"
            "done\n"
            "touch ended\n"
            ,
        ])
        self.assertEqual(self.waitExist(execution.path/'ready',1000), True)
        self.assertEqual((execution.path/'ended').exists(), False)
        found = execution.stop()
        self.assertEqual(found, True)
        self.assertEqual(self.waitExist(execution.path/'ended',1000), True)

    def test_stop_afterProcessEnds_exitsSilently(self):
        execution = Execution(name="One")
        execution.createSandbox()
        p = execution.run([
            "false",
        ])
        p.wait()
        stopped = execution.stop()
        self.assertEqual(stopped, False)

    def test_stop_unlaunched_exitsSilently(self):
        execution = Execution(name="One")
        execution.createSandbox()
        stopped = execution.stop()
        self.assertEqual(stopped, False)

    def test_stop_otherOSErrorsPassThrough(self):
        execution = Execution(name="One")
        execution.createSandbox()
        # Init process (1) belongs to root, cannot send it a signal
        execution.pidFile.write_text("1")
        with self.assertRaises(OSError) as ctx:
            execution.stop()
        self.assertEqual(ctx.exception.errno, errno.EPERM)

    def test_name_byDefault(self):
        execution = Execution(name='')
        self.assertRegex(
            execution.name,
            r'^{:%Y-%m-%d-%H:%M:%S}-[0-9a-f-]{{36}}$'.format(
                datetime.datetime.now()))


    def test_start_namesByDefault(self):
        sandbox = Execution.start(
            command=[
                "bash",
                "-c",
                "touch itworked",
            ])
        self.assertRegex(sandbox,
            r'^{:%Y-%m-%d-%H:%M:%S}-[0-9a-f-]{{36}}$'.format(
                datetime.datetime.now()))
        execution = Execution(sandbox)
        self.waitExist(execution.path/'itworked',1000)

    def test_start_createsSandbox(self):
        sandbox = Execution.start(
            command=[
                "bash",
                "-c",
                "touch itworked",
            ])
        execution = Execution(sandbox)
        self.assertEqual(True, execution.path.exists())
        self.waitExist(execution.path/'itworked',1000)

    def test_start_executesCommand(self):
        sandbox = Execution.start(
            command=[
                "bash",
                "-c",
                "touch itworked",
            ])
        execution = Execution(sandbox)
        self.assertEqual(self.waitExist(execution.path/'itworked',1000), True)

    def test_start_extendChildren(self):
        sandbox = Execution.start(
            command=[
                "bash",
                "-c",
                "touch itworked",
            ])
        execution = Execution(sandbox)
        self.assertIn(execution.pid, children)
        self.assertEqual(children[execution.pid].pid, execution.pid)
        self.waitExist(execution.path/'itworked',1000)


    def test_remove_whenFinished(self):
        execution = Execution(name="One")
        execution.createSandbox()
        p = execution.run([
            "python",
            "-c",
            "from pathlib import Path\n"
            "Path('ended').touch()",
        ])
        p.wait()
        success = execution.remove()
        self.assertEqual(Execution.list(), [])
        self.assertEqual(success, True)

    def test_remove_unstarted(self):
        execution = Execution(name="One")
        execution.createSandbox()
        success = execution.remove()
        self.assertEqual([e.name for e in Execution.list()], ['One'])
        self.assertEqual(success, False)

    def test_remove_unfinished(self):
        execution = Execution(name="One")
        execution.createSandbox()
        p = execution.run([
            "bash",
            "-c",
            "terminated=0\n"
            "function stop() {\n"
            "    touch stopping\n"
            "    terminated=1\n"
            "}\n"
            "trap 'stop' SIGINT\n"
            "touch ready\n"
            "while true; do\n"
            "  [ $terminated == 1 ] && {\n"
            "    break\n"
            "}\n"
            "done\n"
            "touch ended\n"
        ])
        self.waitExist(execution.path/'ready')
        success = execution.remove()
        self.assertEqual([e.name for e in Execution.list()], ['One'])
        self.assertEqual(success, False)
        execution.stop()
        p.wait()


    def test_kill_unstarted(self):
        execution = Execution("One")
        execution.createSandbox()
        found = execution.kill()
        self.assertEqual(found, False)

    def test_kill_finished(self):
        execution = Execution(name="One")
        execution.createSandbox()
        p = execution.run([
            "bash",
            "-c",
            "echo ended\n"
        ])
        p.wait()
        found = execution.kill()
        self.assertEqual(found, False)

    def test_kill_running(self):
        execution = Execution(name="One")
        execution.createSandbox()
        p = execution.run([
            "bash",
            "-c",
            "touch ready\n"
            "while true; do sleep 1; done\n"
        ])
        self.waitExist(execution.path/'ready')
        found = execution.kill()
        self.assertEqual(found, True)

    def test_kill_otherOSErrorsPassThrough(self):
        execution = Execution(name="One")
        execution.createSandbox()
        # Init process (1) belongs to root, cannot send it a signal
        execution.pidFile.write_text("1")
        with self.assertRaises(OSError) as ctx:
            execution.kill()
        self.assertEqual(ctx.exception.errno, errno.EPERM)


    def test_isRunning_beforeRun(self):
        execution = Execution(name="MyExecution")
        self.assertEqual(execution.isRunning, False)

 
    def test_isRunning_whenRunning(self):
        execution = Execution(name="MyExecution")
        execution.createSandbox()
        execution.run([
            'bash',
            '-c',
            "while true; do sleep 1; done"
        ])
        self.assertEqual(execution.isRunning, True)
        execution.kill()

    def test_isRunning_afterRunning(self):
        execution = Execution(name="MyExecution")
        execution.createSandbox()
        p = execution.run([
            'bash',
            '-c',
            "false"
        ])
        p.wait()
        self.assertEqual(execution.isRunning, False)

    def test_isRunning_zombieStatus(self):
        execution = Execution(name="MyExecution")
        execution.createSandbox()
        p = execution.run([
            'bash',
            '-c',
            "touch ended"
        ])
        self.waitExist(execution.path/'ended')
        self.assertEqual(execution.isRunning, False)
        p.wait()

    def test_startTime_sandboxCreated(self):
        execution = Execution("MyExecution")
        execution.createSandbox()
        now = datetime.datetime.utcnow()
        differenceSeconds = (now - execution.startTime).seconds
        self.assertLess(abs(differenceSeconds), 2)

    def test_startTime_sandboxNotCreated(self):
        execution = Execution("MyExecution")
        self.assertEqual(execution.startTime, None)

    def test_listInfo_commonValues(self):
        e = Execution("MyExecution")
        e.createSandbox()
        info = e.listInfo()
        self.assertEqual(info.state, "Launching")
        self.assertEqual(info.name, e.name)
        self.assertEqual(info.startTime, e.startTime)

    def test_listInfo_commonValues_noSandbox(self):
        e = Execution("MyExecution")
        info = e.listInfo()
        self.assertEqual(info.state, "Launching")
        self.assertEqual(info.name, e.name)
        self.assertEqual(info.startTime, None)



# vim: ts=4 sw=4 et
