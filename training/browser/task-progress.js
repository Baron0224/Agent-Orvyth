window.OrvythTaskProgress = {
  render(entry, task) {
    let box=entry.querySelector('.task-progress');
    if(!box){box=document.createElement('details');box.className='task-progress';entry.querySelector('.label').after(box);}
    const wasOpen=box.open;box.replaceChildren();box.dataset.state=task.state;
    const summary=document.createElement('summary');
    summary.textContent=({running:'正在处理 · 查看进度',completed:'任务已完成 · 查看执行记录',failed:'任务未完成 · 查看原因'})[task.state]||'执行记录';
    const list=document.createElement('ol');
    for(const step of task.steps||[]){const row=document.createElement('li');row.textContent=step.label;if(step.path){const detail=document.createElement('small');detail.textContent=step.path;row.append(detail);}list.append(row);}
    box.append(summary,list);box.open=wasOpen||task.state==='failed';
  }
};
