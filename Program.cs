using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

namespace JanesCriberLauncher
{
    static class Program
    {
        [STAThread]
        static void Main()
        {
            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string studioExe = Path.Combine(baseDir, "JanesCriberStudio.exe");
            if (File.Exists(studioExe))
            {
                try
                {
                    ProcessStartInfo psiStudio = new ProcessStartInfo
                    {
                        FileName = studioExe,
                        WorkingDirectory = baseDir,
                        UseShellExecute = true
                    };
                    Process.Start(psiStudio);
                    return;
                }
                catch (Exception ex)
                {
                    MessageBox.Show(
                        "JanesCriber Studio could not start:\n\n" + ex.Message,
                        "JanesCriber - Launch Error",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Error
                    );
                    return;
                }
            }

            string[] candidates = new string[]
            {
                Path.Combine(baseDir, ".venv", "Scripts", "pythonw.exe"),
                Path.Combine(baseDir, "venv", "Scripts", "pythonw.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "Python", "Python312", "pythonw.exe"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs", "Python", "Python311", "pythonw.exe"),
                @"C:\Python312\pythonw.exe",
                @"C:\Python311\pythonw.exe",
                @"C:\Python310\pythonw.exe"
            };

            string pythonExe = "pythonw.exe";
            foreach (string candidate in candidates)
            {
                if (File.Exists(candidate))
                {
                    pythonExe = candidate;
                    break;
                }
            }

            try
            {
                ProcessStartInfo psi = new ProcessStartInfo
                {
                    FileName = pythonExe,
                    Arguments = "-m janescriber --gui",
                    WorkingDirectory = baseDir,
                    UseShellExecute = true,
                    CreateNoWindow = true,
                    WindowStyle = ProcessWindowStyle.Hidden
                };
                Process.Start(psi);
            }
            catch (System.ComponentModel.Win32Exception)
            {
                MessageBox.Show(
                    "Python was not found. Run setup.bat in this folder first to install JanesCriber.",
                    "JanesCriber - Setup Required",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Warning
                );
            }
            catch (Exception ex)
            {
                MessageBox.Show(
                    "JanesCriber could not start:\n\n" + ex.Message,
                    "JanesCriber - Launch Error",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
            }
        }
    }
}
