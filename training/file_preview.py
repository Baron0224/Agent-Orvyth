"""候选图片预览：路径只从当前聊天的服务端记录取得。"""
import io, os, warnings
from pathlib import Path
from urllib.parse import urlencode
from file_lookup import search_roots

IMAGE_TYPES={'.png','.jpg','.jpeg','.webp'}
MAX_BYTES=8*1024*1024

def cards(chat, message, evidence):
    if not evidence or evidence.get('kind')!='file_lookup':return []
    result=[]
    for index,value in enumerate(evidence.get('paths',[])[:8]):
        if evidence.get('selected_index') is not None and index != evidence['selected_index']:continue
        path=Path(value)
        result.append({'name':f'{index+1}. {path.name}','path':str(path),'kind':'directory' if path.is_dir() else 'file','match':evidence.get('match','unverified'),'notice':'仅按名称定位，内容与用途未核实','preview_url':'/api/file-preview?'+urlencode({'chat':chat,'message':message,'index':index}) if path.suffix.lower() in IMAGE_TYPES else None})
    return result

def preview(path, evidence):
    path=Path(path)
    def check():
        if path.suffix.lower() not in IMAGE_TYPES or not path.is_absolute() or '..' in path.parts:raise ValueError('不支持预览此文件类型。')
        for part in (path,*path.parents):
            if part.is_symlink() or (hasattr(part,'is_junction') and part.is_junction()):raise ValueError('不能预览链接路径。')
        resolved=path.resolve(strict=True)
        roots=[Path(p).resolve() for p in search_roots()]
        saved=[Path(p).resolve() for p in evidence.get('roots',[])]
        if not any(resolved.is_relative_to(root) for root in roots) or not any(resolved.is_relative_to(root) for root in saved):raise ValueError('候选不在允许的搜索范围内。')
        if not resolved.is_file() or resolved.stat().st_size>MAX_BYTES:raise ValueError('图片不存在或超过8MB。')
        return resolved
    resolved=check()
    with resolved.open('rb') as stream:
        raw=stream.read(MAX_BYTES+1)
        if len(raw)>MAX_BYTES or check().stat().st_ino!=os.fstat(stream.fileno()).st_ino:raise ValueError('文件已变化，请重新查找。')
    from PIL import Image,ImageOps
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as original:
                if original.width*original.height>16_000_000:raise ValueError('图片像素过大。')
                image=ImageOps.exif_transpose(original).convert('RGB');image.thumbnail((2048,2048))
                output=io.BytesIO();image.save(output,format='PNG');return output.getvalue()
    except (Image.DecompressionBombError,Image.DecompressionBombWarning):raise ValueError('图片像素过大。') from None
