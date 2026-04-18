/**
 * PaperForge — Electron Main Process
 * Desktop application wrapper for the PaperForge converter.
 */
const { app, BrowserWindow, ipcMain, dialog, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

let mainWindow;
const isDev = process.argv.includes('--dev');

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    title: 'PaperForge — Academic Paper Converter',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
    backgroundColor: '#0f1117',
  });

  // Load the React frontend
  if (isDev) {
    mainWindow.loadURL('http://localhost:3000');
    mainWindow.webContents.openDevTools();
  } else {
    // In production, serve the built React app
    const indexPath = path.join(__dirname, '..', 'web', 'frontend', 'dist', 'index.html');
    if (fs.existsSync(indexPath)) {
      mainWindow.loadFile(indexPath);
    } else {
      // Fallback: load a simple HTML page
      mainWindow.loadFile(path.join(__dirname, 'fallback.html'));
    }
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (mainWindow === null) createWindow();
});

// ── IPC Handlers ───────────────────────────────────────────────────

// File selection dialog
ipcMain.handle('select-file', async (event, options) => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile'],
    filters: [
      { name: 'Documents', extensions: ['docx', 'doc', 'tex', 'md', 'jats', 'xml'] },
      { name: 'All Files', extensions: ['*'] },
    ],
  });
  return result.canceled ? null : result.filePaths[0];
});

// Folder selection dialog
ipcMain.handle('select-folder', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory'],
  });
  return result.canceled ? null : result.filePaths[0];
});

// Save dialog
ipcMain.handle('save-file', async (event, defaultName) => {
  const result = await dialog.showSaveDialog(mainWindow, {
    defaultPath: defaultName,
    filters: [
      { name: 'Word Document', extensions: ['docx'] },
      { name: 'PDF', extensions: ['pdf'] },
      { name: 'LaTeX', extensions: ['tex'] },
      { name: 'HTML', extensions: ['html'] },
    ],
  });
  return result.canceled ? null : result.filePath;
});

// Run pipeline
ipcMain.handle('run-pipeline', async (event, args) => {
  const { inputFile, journal, format, outputDir, bibliography } = args;

  return new Promise((resolve, reject) => {
    const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
    const projectRoot = isDev
      ? path.join(__dirname, '..')
      : process.resourcesPath;

    const scriptPath = path.join(projectRoot, 'pipeline', 'translator.py');

    const cmdArgs = [
      scriptPath,
      inputFile,
      '--journal', journal,
      '--format', format,
      '--quiet',
    ];

    if (outputDir) {
      cmdArgs.push('--output', outputDir);
    }
    if (bibliography) {
      cmdArgs.push('--bibliography', bibliography);
    }

    const proc = spawn(pythonCmd, cmdArgs, {
      cwd: projectRoot,
      env: { ...process.env, PYTHONPATH: projectRoot },
    });

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (data) => {
      stdout += data.toString();
      // Send progress updates
      mainWindow?.webContents?.send('pipeline-progress', {
        type: 'stdout',
        data: data.toString(),
      });
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
      mainWindow?.webContents?.send('pipeline-progress', {
        type: 'stderr',
        data: data.toString(),
      });
    });

    proc.on('close', (code) => {
      // Find output files
      const outputs = {};
      if (outputDir) {
        const files = fs.readdirSync(outputDir);
        for (const file of files) {
          if (file.endsWith('.docx')) outputs.docx = path.join(outputDir, file);
          if (file.endsWith('.pdf')) outputs.pdf = path.join(outputDir, file);
          if (file.endsWith('.tex')) outputs.latex = path.join(outputDir, file);
          if (file.endsWith('.html')) outputs.html = path.join(outputDir, file);
        }
      }

      resolve({
        success: code === 0,
        exitCode: code,
        stdout,
        stderr,
        outputs,
      });
    });

    proc.on('error', (err) => {
      reject({ success: false, error: err.message });
    });
  });
});

// Open file in default app
ipcMain.handle('open-file', async (event, filePath) => {
  shell.openPath(filePath);
});

// Get system info
ipcMain.handle('get-system-info', async () => {
  return {
    platform: process.platform,
    arch: process.arch,
    nodeVersion: process.version,
    appVersion: app.getVersion(),
  };
});

// List journals
ipcMain.handle('list-journals', async () => {
  const projectRoot = isDev
    ? path.join(__dirname, '..')
    : process.resourcesPath;

  // Read template manifest if exists
  const manifestPath = path.join(projectRoot, 'templates', 'manifest.json');
  if (fs.existsSync(manifestPath)) {
    return JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
  }

  // Return built-in list
  return {
    ieee: { name: 'IEEE Transactions', class: 'IEEEtran' },
    springer: { name: 'Springer Nature', class: 'sn-jnl' },
    wiley: { name: 'Wiley', class: 'wiley-article' },
    elsevier: { name: 'Elsevier', class: 'elsarticle' },
    mdpi: { name: 'MDPI', class: 'mdpi' },
    nature: { name: 'Nature', class: 'nature' },
    acm: { name: 'ACM', class: 'acmart' },
  };
});
