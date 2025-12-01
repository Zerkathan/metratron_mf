# 📝 Instrucciones para Crear el Repositorio en GitHub

## Pasos Completados ✅

1. ✅ Repositorio Git inicializado
2. ✅ `.gitignore` creado
3. ✅ `README.md` creado
4. ✅ Commit inicial realizado

## Próximos Pasos

### Opción 1: Usando GitHub CLI (Recomendado)

Si tienes `gh` CLI instalado:

```powershell
# Autenticarse con GitHub
gh auth login

# Crear el repositorio y conectar
gh repo create metratron_bot --public --source=. --remote=origin --push
```

### Opción 2: Manualmente desde GitHub Web

1. **Crear el repositorio en GitHub:**
   - Ve a https://github.com/new
   - Nombre: `metratron_bot` (o el que prefieras)
   - Descripción: "Sistema profesional de generación automática de videos virales con IA"
   - Visibilidad: Público o Privado (según prefieras)
   - **NO** inicialices con README, .gitignore o licencia (ya los tenemos)
   - Click en "Create repository"

2. **Conectar el repositorio local con GitHub:**
   ```powershell
   git remote add origin https://github.com/TU-USUARIO/metratron_bot.git
   git branch -M main
   git push -u origin main
   ```

   Reemplaza `TU-USUARIO` con tu nombre de usuario de GitHub.

### Opción 3: Usando GitHub Desktop

1. Abre GitHub Desktop
2. File → Add Local Repository
3. Selecciona la carpeta `C:\Metratron_bot`
4. Click en "Publish repository"
5. Sigue las instrucciones en pantalla

## Verificar

Después de hacer push, verifica que todo esté bien:

```powershell
git remote -v
git status
```

## Notas Importantes

- El repositorio ya tiene un commit inicial con todos los archivos del código
- El `.gitignore` excluye archivos sensibles (`.env`, tokens, etc.)
- El `.venv/` no está incluido (debe recrearse en cada máquina)
- Los videos generados (`.mp4`) están excluidos por tamaño

## Si necesitas actualizar el repositorio después

```powershell
git add .
git commit -m "Descripción de los cambios"
git push
```






