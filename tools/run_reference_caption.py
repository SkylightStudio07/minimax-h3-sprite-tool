"""One CPU inference process; exit releases the caption model and image memory."""
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def main():
    import torch
    from transformers import AutoProcessor,Qwen3VLForConditionalGeneration
    import image_caption
    torch.set_num_threads(min(8,os.cpu_count() or 4))
    processor=AutoProcessor.from_pretrained(image_caption.MODEL_DIR,local_files_only=True,trust_remote_code=False)
    # Preserve the prepared image's detail instead of reducing it to ~512px.
    processor.image_processor.size={'shortest_edge':65536,'longest_edge':768*768}
    model=Qwen3VLForConditionalGeneration.from_pretrained(image_caption.MODEL_DIR,local_files_only=True,trust_remote_code=False,dtype=torch.float32).eval()
    messages=[{'role':'user','content':[{'type':'image','image':str(Path(sys.argv[1]).resolve())},
                 {'type':'text','text':image_caption.INSTRUCTION}]}]
    inputs=processor.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,return_dict=True,return_tensors='pt')
    with torch.inference_mode():
        tokens=model.generate(**inputs,max_new_tokens=image_caption.MAX_NEW_TOKENS,do_sample=False,
                              repetition_penalty=1.1,no_repeat_ngram_size=6)
    text=processor.batch_decode(tokens[:,inputs['input_ids'].shape[1]:],skip_special_tokens=True)[0].strip()
    if text.startswith('```'):
        text=text.split('\n',1)[1].rsplit('```',1)[0].strip()
    # Only ask the vision model for appearance text. The server owns the JSON
    # envelope so longer descriptions cannot break it with an unfinished brace.
    if tokens.shape[1]-inputs['input_ids'].shape[1]>=image_caption.MAX_NEW_TOKENS:
        if ',' in text:text=text.rsplit(',',1)[0].strip()
        elif '. ' in text:text=text.rsplit('. ',1)[0].strip()+'.'
    data=dict(prompt=text,summary='후드·의상·소품을 원본과 비교해 주세요.')
    print(json.dumps(data,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
