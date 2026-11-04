import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,symlink,realpath,rm} from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {projectPath} from './project-path.mjs';
test('project reads reject traversal, credentials, absolute paths and symlink escapes',async()=>{
 const base=await mkdtemp(path.join(os.tmpdir(),'orvyth-path-test-'));
 try{
  await mkdir(path.join(base,'project'));const root=await realpath(path.join(base,'project'));
  await writeFile(path.join(root,'README.md'),'hello');await writeFile(path.join(base,'outside.txt'),'outside');
  assert.equal(await projectPath(root,'README.md'),path.join(root,'README.md'));
  await assert.rejects(projectPath(root,'../outside.txt'));
  await assert.rejects(projectPath(root,path.join(base,'outside.txt')));
  await writeFile(path.join(root,'.env'),'private');await assert.rejects(projectPath(root,'.env'));
  await symlink(base,path.join(root,'escape'),'junction');await assert.rejects(projectPath(root,'escape/outside.txt'));
 }finally{await rm(base,{recursive:true,force:true});}
});
