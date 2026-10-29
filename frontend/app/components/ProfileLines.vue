<script setup lang="ts">
defineProps<{ modelValue:string[], label:string, hint?:string }>()
const emit = defineEmits<{ 'update:modelValue':[value:string[]] }>()
</script>
<template><label class="profile-field">{{ label }}<textarea :value="modelValue.join('\n')" rows="3" @input="emit('update:modelValue',($event.target as HTMLTextAreaElement).value.split('\n'))" /><small>{{ hint || 'One item per line.' }}</small></label></template>
