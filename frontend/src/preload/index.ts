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
  setBackendUrl: (url: string) => ipcRenderer.invoke('set-backend-url', url),
  // Phase 15b — local action executor (approval-gated shell/file/app on the
  // owner's machine). The renderer calls these to run approved local actions.
  localExecutor: {
    authorize: (payload: any) => ipcRenderer.invoke('local-action:authorize', payload),
    execute: (payload: any) => ipcRenderer.invoke('local-action:execute', payload),
    revoke: (id: string) => ipcRenderer.invoke('local-action:revoke', id),
    getState: () => ipcRenderer.invoke('local-action:state'),
    listAllowlist: () => ipcRenderer.invoke('local-action:allowlist:list'),
    addAllowlist: (entry: string) => ipcRenderer.invoke('local-action:allowlist:add', entry),
    removeAllowlist: (entry: string) => ipcRenderer.invoke('local-action:allowlist:remove', entry)
  }
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
