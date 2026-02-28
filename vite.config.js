import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
    plugins: [react()],
    root: path.resolve(__dirname, 'src/presentation/web/static'),
    base: '/static/',
    build: {
        outDir: path.resolve(__dirname, 'src/presentation/web/static/dist'),
        emptyOutDir: true,
        lib: {
            entry: path.resolve(__dirname, 'src/presentation/web/static/js/index.js'),
            name: 'SGUBM',
            formats: ['iife'],
            fileName: () => 'bundle.js',
        },
        rollupOptions: {
            output: {
                assetFileNames: (assetInfo) => {
                    if (assetInfo.name.endsWith('.css')) return 'bundle.css';
                    return assetInfo.name;
                },
            },
        },
    },
    resolve: {
        alias: {
            '@': path.resolve(__dirname, 'src/presentation/web/static/js'),
        },
    },
});
