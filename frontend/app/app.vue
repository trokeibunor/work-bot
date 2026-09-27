<script setup lang="ts">
import VelocityBar from '~/components/VelocityBar.vue'
</script>

<template>
  <div class="min-h-screen bg-dark-950 text-slate-100 flex flex-col font-sans">
    <!-- Persistent Velocity Header -->
    <VelocityBar />

    <!-- Main Page Router View -->
    <main class="flex-1 w-full max-w-7xl mx-auto px-4 lg:px-8 py-6">
      <NuxtPage />
    </main>

    <!-- Footer -->
    <footer class="py-4 border-t border-white/5 text-center text-xs text-slate-500 font-mono">
      JATE v1.0.0 &bull; Automated Job Ingestion & Tracking Engine &bull; Contabo VPS Optimized
    </footer>
  </div>
</template>
