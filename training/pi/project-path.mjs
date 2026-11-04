import {realpath} from 'node:fs/promises';
import path from 'node:path';
export const blocked = name => /^(node_modules|\.git|\.venv|venv|\.pi|\.ssh|\.aws|\.env.*|auth\.json|credentials.*)$/i.test(name) || /\.(pem|key|p12|sqlite3?|db)$/i.test(name);
export async function projectPath(root, relative='.') {
 if(typeof relative!=='string'||path.isAbsolute(relative)||relative.split(/[\\/]/).some(p=>blocked(p)||p.includes(':'))) throw new Error('仅能读取项目内的普通文件。');
 const target=await realpath(path.resolve(root,relative)), rel=path.relative(root,target);
 if(rel==='..'||rel.startsWith('..'+path.sep)||path.isAbsolute(rel)||rel.split(path.sep).some(blocked))throw new Error('路径超出项目范围。');
 return target;
}
