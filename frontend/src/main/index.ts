import { app, shell, BrowserWindow, ipcMain } from 'electron'
import { join } from 'path'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import Store from 'electron-store'
import { LocalActionExecutor } from './local-executor'

const store = new Store()

// Phase 15b — the main-process local action executor: runs approved shell /
// file / app actions on the owner's machine, gated by approval + allowlist +
// destructive-op confirmation. The backend remains the approval authority and
// still enforces hosted-mode blocking server-side.
const localExecutor = new LocalActionExecutor({
  persistAllowlist: (list) => store.set('local-executor-allowlist', list)
})
const persistedAllowlist = (store.get('local-executor-allowlist') as string[]) || undefined
localExecutor.loadAllowlist(persistedAllowlist as string[])

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

  // --- Phase 15b Local Action Executor IPC surface -------------------------
  // The renderer (chat loop) calls these to run an owner-approved local
  // action on the owner's machine and get the result back into the chat.
  ipcMain.handle('local-action:authorize', (_, payload) => localExecutor.authorize(payload))
  ipcMain.handle('local-action:execute', (_, payload) => localExecutor.execute(payload))
  ipcMain.handle('local-action:revoke', (_, id) => localExecutor.revoke(id))
  ipcMain.handle('local-action:state', () => localExecutor.getState())
  ipcMain.handle('local-action:allowlist:list', () => localExecutor.listAllowlist())
  ipcMain.handle('local-action:allowlist:add', (_, entry) => localExecutor.addAllowlist(entry))
  ipcMain.handle('local-action:allowlist:remove', (_, entry) => localExecutor.removeAllowlist(entry))

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
