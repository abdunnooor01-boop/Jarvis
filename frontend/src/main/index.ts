import { app, shell, BrowserWindow, ipcMain } from 'electron'
import { join } from 'path'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import Store from 'electron-store'

const store = new Store()

function createWindow(): void {
  const mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    show: false,
    autoHideMenuBar: true,
    titleBarStyle: 'hiddenInset',
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false
    }
  })

  mainWindow.on('ready-to-show', () => {
    mainWindow.show()
  })

  mainWindow.webContents.setWindowOpenHandler((details) => {
    shell.openExternal(details.url)
    return { action: 'deny' }
  })

  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

app.whenReady().then(() => {
  electronApp.setAppUserModelId('com.shipwright.jarvis')

  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  // IPC handlers for store
  ipcMain.handle('store-get', (_, key) => store.get(key))
  ipcMain.handle('store-set', (_, key, value) => store.set(key, value))
  ipcMain.handle('store-delete', (_, key) => store.delete(key))

  // Custom IPC handlers for dynamic backend URL configuration
  // The desktop app is a LOCAL companion: it talks to the local Jarvis
  // backend (FastAPI on localhost:8000) by default. JARVIS_BACKEND_URL /
  // VITE_API_URL / the stored value override that for hosted deployments.
  ipcMain.on('get-backend-url-sync', (event) => {
    event.returnValue = process.env.JARVIS_BACKEND_URL || process.env.VITE_API_URL || store.get('backend-url') || 'http://localhost:8000'
  })
  ipcMain.handle('get-backend-url', () => {
    return process.env.JARVIS_BACKEND_URL || process.env.VITE_API_URL || store.get('backend-url') || 'http://localhost:8000'
  })
  ipcMain.handle('set-backend-url', (_, url) => {
    store.set('backend-url', url)
    return true
  })

  createWindow()

  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
