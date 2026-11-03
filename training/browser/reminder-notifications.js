/* System notifications for active local pages. No network push is used. */
(function () {
  function create(options) {
    const sent = new Set(), failures = new Set();
    function supported() { return typeof options.Notification === 'function'; }
    function permission() { return supported() ? options.Notification.permission : 'unsupported'; }
    function key(task) { return `orvyth.notice.v1:${task.id}:${task.due_at ?? task.occurrence_date}`; }
    function isSent(id) { try { return sent.has(id) || options.storage.getItem(id) === '1'; } catch { return sent.has(id); } }
    function mark(id) { sent.add(id); try { options.storage.setItem(id, '1'); } catch {} }
    function unmark(id) { sent.delete(id); try { options.storage.removeItem(id); } catch {} }
    function notify(task) {
      if (!task.remind_due || permission() !== 'granted') return false;
      const id = key(task); if (isSent(id) || failures.has(id)) return false;
      mark(id);
      try {
        const notification = new options.Notification('Orvyth 提醒', {body: task.title, tag: id});
        notification.onclick = () => { options.focus(); notification.close(); };
        notification.onerror = () => { unmark(id); failures.add(id); options.failed(); };
        return true;
      } catch { unmark(id); failures.add(id); options.failed(); return false; }
    }
    function retry() { failures.clear(); }
    return {supported, permission, notify, retry};
  }
  window.OrvythNotifications = {create};
})();
