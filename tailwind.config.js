/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
        "./src/presentation/web/templates/**/*.html",
        "./src/presentation/web/static/js/**/*.js",
        "./src/presentation/web/static/js/**/*.jsx",
    ],
    theme: {
        extend: {
            colors: {
                premium: {
                    primary: '#4f46e5',
                    secondary: '#7c3aed',
                    accent: '#ec4899',
                }
            },
            backdropBlur: {
                glass: '10px',
            }
        },
    },
    plugins: [],
}
