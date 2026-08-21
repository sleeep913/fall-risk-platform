<script setup lang="ts">
withDefaults(
  defineProps<{
    status: 'ok' | 'error' | 'disabled' | 'pending'
    label: string
  }>(),
  { status: 'pending' },
)
</script>

<template>
  <span class="status-pill" :class="`status-pill--${status}`">
    <span class="status-pill__dot" aria-hidden="true" />
    {{ label }}
  </span>
</template>
