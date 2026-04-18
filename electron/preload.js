/**
 * PaperForge — Electron Preload Script
 * Exposes safe IPC methods to the renderer process.
 */
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('paperforge', {
  // File dialogs
  selectFile: () => ipcRenderer.invoke('select-file'),
  selectFolder: () => ipcRenderer.invoke('select-folder'),
  saveFile: (defaultName) => ipcRenderer.invoke('save-file', defaultName),

  // Pipeline
  runPipeline: (args) => ipcRenderer.invoke('run-pipeline', args),
  onProgress: (callback) => {
    ipcRenderer.on('pipeline-progress', (event, data) => callback(data));
  },

  // File operations
  openFile: (path) => ipcRenderer.invoke('open-file', path),

  // System
  getSystemInfo: () => ipcRenderer.invoke('get-system-info'),
  listJournals: () => ipcRenderer.invoke('list-journals'),
});
