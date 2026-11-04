import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,readFile,rm,access} from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {binary,cli,readDocx,replaceDocx} from './docx-tools.mjs';
test('Word reads, edits a copy, preserves original and rejects invalid operations',async t=>{
 try{await access(binary());}catch{t.skip('Run setup-docx.ps1 first');return;}
 const dir=await mkdtemp(path.join(os.tmpdir(),'orvyth-docx-test-'));
 try{
  const source=path.join(dir,'sample.docx');
  await cli(['create',source,'--text','今天学习Word编辑。']);
  const original=await readFile(source);
  assert.match(await readDocx(dir,'sample.docx'),/今天学习Word编辑/);
  const output=await replaceDocx(dir,'sample.docx','Word','文档');
  assert.match(await readDocx(dir,output),/今天学习文档编辑/);
  assert.deepEqual(await readFile(source),original);
  await assert.rejects(replaceDocx(dir,'sample.docx','没有这句话','替换'));
  await assert.rejects(readDocx(dir,'../outside.docx'));
 }finally{await rm(dir,{recursive:true,force:true});}
});
