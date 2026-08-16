import { contextBridge, ipcRenderer } from 'electron'
import { electronAPI } from '@electron-toolkit/preload'

const api = {
  store: {
    get: (key: string) => ipcRenderer.invoke('store-get', key),
    set: (key: string, value: any) => ipcRenderer.invoke('store-set', key, value),
    delete: (key: string) => ipcRenderer.invoke('store-delete', key)
  },
  getBackendUrlSync: () => ipcRenderer.sendSync('get-backend-url-sync'),
  getBackendUrl: () => ipcRenderer.invoke('get-backend-url'),
  setBackendUrl: (url: string) => ipcRenderer.invoke('set-backend-url', url)
}

if (process.contextIsolated) {
  try {
    contextBridge.exposeInMainWorld('electron', electronAPI)
    contextBridge.exposeInMainWorld('api', api)
  } catch (error) {
    console.error(error)
  }
} else {
  // @ts-ignore (define in dts)
  window.electron = electronAPI
  // @ts-ignore (define in dts)
  window.api = api
}
