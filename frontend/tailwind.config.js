/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        brand:  { DEFAULT:'#0F6E56', light:'#E1F5EE', mid:'#1D9E75', dark:'#085041' },
        amber:  { DEFAULT:'#BA7517', light:'#FAEEDA' },
        danger: { DEFAULT:'#A32D2D', light:'#FCEBEB' },
        info:   { DEFAULT:'#185FA5', light:'#E6F1FB' },
      }
    }
  },
  plugins: []
}
