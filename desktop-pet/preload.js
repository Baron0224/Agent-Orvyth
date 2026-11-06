'use strict';
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('pet', {
  dragStart: () => ipcRenderer.send('pet:drag-start'),
  dragEnd: () => ipcRenderer.send('pet:drag-end'),
  setIgnore: (ignore) => ipcRenderer.send('pet:ignore', !!ignore),
  ask: (text) => ipcRenderer.invoke('pet:ask', text),
  onDelta: (callback) => {
    const listener = (_event, text) => callback(text);
    ipcRenderer.on('pet:delta', listener);
    return () => ipcRenderer.removeListener('pet:delta', listener);
  },
  openChat: () => ipcRenderer.send('pet:open-chat'),
  quit: () => ipcRenderer.send('pet:quit')
});
