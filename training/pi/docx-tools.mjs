import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {copyFile, constants, mkdtemp, rm, stat} from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import {projectPath} from './project-path.mjs';
const execute=promisify(execFile);
export const binary=()=>process.env.ORVYTH_DOCX_CLI || path.join(process.env.LOCALAPPDATA || '', 'Orvyth/tools/docx-cli/v0.27.0/docx.exe');
export async function cli(args){
 try { const {stdout}=await execute(binary(),args,{windowsHide:true,timeout:30000,maxBuffer:1024*1024}); return stdout; }
 catch(error){throw new Error((error.stdout || error.message).slice(0,2000));}
}
export async function readDocx(root,file){
 const target=await projectPath(root,file);
 if(path.extname(target).toLowerCase()!=='.docx' || (await stat(target)).size>20*1024*1024) throw new Error('请选择20MB以内的 .docx 文件。');
 return (await cli(['read',target])).slice(0,16000);
}
export async function replaceDocx(root,file,oldText,newText){
 if(typeof oldText!=='string'||!oldText||typeof newText!=='string'||oldText.length+newText.length>12000)throw new Error('请提供原文和12000字以内的新内容。');
 const source=await projectPath(root,file);
 await readDocx(root,file);
 const temp=await mkdtemp(path.join(os.tmpdir(),'orvyth-docx-'));
 const working=path.join(temp,'working.docx');
 try {
  await copyFile(source,working);
  // stdin JSONL keeps text out of command-line option parsing.
  const batch=path.join(temp,'edits.jsonl');
  const {writeFile}=await import('node:fs/promises');
  await writeFile(batch,JSON.stringify({pattern:oldText,replacement:newText,all:false})+'\n');
  await cli(['replace',working,'--batch',batch]);
  await cli(['validate',working]);
  const output=path.join(path.dirname(source),path.basename(source,'.docx')+'-修改-'+Date.now()+'.docx');
  await copyFile(working,output,constants.COPYFILE_EXCL);
  return path.relative(root,output);
 } finally {await rm(temp,{recursive:true,force:true});}
}
