<script setup lang="ts">
const props = defineProps<{ text: string }>()
// Vue renders source text; no HTML from profiles, job listings, or generated drafts is trusted.
const blocks = computed(() => {
  const result:{tag:string,lines:string[]}[]=[]
  let current:{tag:string,lines:string[]}|null=null
  const flush=()=>{if(current){result.push(current);current=null}}
  for(const line of (props.text||'').split('\n')) {
    if(!line.trim()){flush();continue}
    if(/^#{1,4}\s/.test(line)){flush();result.push({tag:'h3',lines:[line.replace(/^#{1,4}\s+/,'')]});continue}
    const list=/^\s*[-*]\s+/.test(line),tag=list?'ul':'p'
    if(current?.tag!==tag){flush();current={tag,lines:[]}}
    current!.lines.push(list?line.replace(/^\s*[-*]\s+/,''):line)
  }
  flush();return result
})
const parts = (text:string) => text.split(/(\*\*[^*]+\*\*|__[^_]+__)/g).filter(Boolean).map(value=>({bold:/^(\*\*|__)/.test(value),text:/^(\*\*|__)/.test(value)?value.slice(2,-2):value}))
</script>
<template><div class="document-copy"><component :is="block.tag" v-for="(block,index) in blocks" :key="index"><template v-if="block.tag==='ul'"><li v-for="(line,i) in block.lines" :key="i"><component :is="part.bold?'strong':'span'" v-for="(part,j) in parts(line)" :key="j">{{ part.text }}</component></li></template><template v-else><template v-for="(line,i) in block.lines" :key="i"><br v-if="i"><component :is="part.bold?'strong':'span'" v-for="(part,j) in parts(line)" :key="j">{{ part.text }}</component></template></template></component></div></template>
