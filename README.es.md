# quantum-lab

[![Build](https://github.com/Ethan-Rivas/quantum-lab/actions/workflows/build.yml/badge.svg)](https://github.com/Ethan-Rivas/quantum-lab/actions/workflows/build.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Plataformas](https://img.shields.io/badge/plataformas-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey.svg)

**Un laboratorio de computación cuántica que corre en tu propia computadora.** Qiskit, Cirq y pyQuil en JupyterLab, listos con un solo comando.

[Read in English](README.md)

Armé esto mientras estudio mi maestría en computación cuántica. La parte cuántica fue la divertida. Lo complicado fue tener un entorno local que funcionara: instalar Qiskit con Anaconda siempre terminaba fallando en mi Mac, y no encontré un entorno listo que hiciera lo que necesitaba, así que terminé usando Google Colab. Colab funciona, pero en cada sesión hay que reinstalar los paquetes, y se desconecta si te alejas un rato. Este repo es el entorno que yo quería: los mismos notebooks, todo ya instalado y tus archivos guardados en tu propia máquina. Lo comparto para que el siguiente se salte la instalación y vaya directo a los qubits.

## Qué necesitas

[Docker Desktop](https://www.docker.com/products/docker-desktop/) para macOS, Windows o Linux. Nada más. Python, Jupyter y las librerías cuánticas viven dentro de los contenedores, así que no se instala nada en tu sistema.

## Inicio rápido

```bash
git clone https://github.com/Ethan-Rivas/quantum-lab.git
cd quantum-lab
docker compose up
```

La primera vez descarga y construye todo, así que tarda unos minutos. Después arranca en segundos.

Luego abre **http://127.0.0.1:8888/lab?token=quantum**, abre `00-hello-quantum.ipynb` y ejecuta las celdas con **Shift + Enter**.

Cuando termines, presiona **Ctrl + C** en la terminal o ejecuta `docker compose down`. Tus notebooks se guardan en la carpeta `notebooks/`, así que no pierdes nada al apagar el laboratorio.

## Tu primer experimento

El notebook de inicio construye un **estado de Bell**, el ejemplo más sencillo de entrelazamiento:

1. Una compuerta Hadamard pone al primer qubit en superposición de 0 y 1.
2. Una compuerta CNOT enlaza el segundo qubit con el primero.
3. Se miden ambos qubits, 1,000 veces.

Vas a obtener `00` más o menos la mitad de las veces y `11` la otra mitad, pero nunca `01` ni `10`. Cada qubit por separado es un volado, pero los dos siempre coinciden. Eso es el entrelazamiento.

El notebook ejecuta este mismo circuito en Qiskit, Cirq y pyQuil y grafica los resultados lado a lado, para que compares cómo lo escribe cada framework. Al final incluye un pequeño ejemplo del algoritmo de búsqueda de Grover.

## Qué hay en el laboratorio

| Herramienta | Qué es |
|---|---|
| **Qiskit** + **Aer** | El framework de IBM, y el más usado. Aer es su simulador rápido. IBM también te deja ejecutar circuitos de Qiskit en sus computadoras cuánticas reales. |
| **Cirq** | El framework de Google. De más bajo nivel que Qiskit, y más cercano a cómo está organizado el hardware. |
| **pyQuil** + **QVM** + **quilc** | El framework de Rigetti. quilc compila tu circuito a las compuertas que soporta un chip real, y la QVM lo simula. Cada uno corre en su propio contenedor. |
| **JupyterLab** | La misma interfaz de notebooks en la que está basado Colab, con explorador de archivos, pestañas y terminal. |

## ¿Vienes de Colab?

- Descarga cualquier notebook de Colab (*Archivo → Descargar → .ipynb*) y ponlo en `notebooks/`.
- Quita las líneas exclusivas de Colab, como `from google.colab import drive`.
- Sáltate las celdas con `!pip install qiskit`. Todo ya está instalado.
- No hay GPU, pero los simuladores cuánticos a escala de aprendizaje corren en el CPU de todos modos.

## Otras formas de usarlo

**Sin los servidores de Rigetti.** Arranca más rápido. pyQuil usa su simulador integrado en Python:

```bash
docker compose up --no-deps notebook
```

**VS Code o GitHub Codespaces.** Abre el repo en VS Code y elige *Reopen in Container*, o en GitHub haz clic en *Code → Codespaces → Create codespace*. Codespaces corre todo el laboratorio en la nube, así que sirve como reemplazo de Colab cuando no estás en tu computadora.

**Imagen precompilada.** Evita el paso de construcción y descarga una imagen ya lista:

```bash
docker compose -f docker-compose.yml -f docker-compose.prebuilt.yml up
```

Eso usa `latest`, que se reconstruye cada semana. Para quedarte en una versión específica, cambia la imagen en `docker-compose.prebuilt.yml` por una etiqueta de versión como `ghcr.io/ethan-rivas/quantum-lab:0.1.0`.

**Sin Docker.** Si solo necesitas Qiskit y Cirq, [uv](https://docs.astral.sh/uv/) puede correr el laboratorio directamente (`brew install uv` en Mac):

```bash
uvx -p 3.12 --from jupyter-core --with jupyterlab --with "qiskit[visualization]" \
    --with qiskit-aer --with cirq --with "pyquil<5" jupyter lab
```

Aquí pyQuil usa su simulador integrado. No quites el `-p 3.12`, porque pyQuil todavía no se instala en Python 3.13.

## Verifica que todo funcione

Con el laboratorio corriendo, abre otra terminal y ejecuta:

```bash
docker compose exec notebook python /opt/quantum-lab/smoke_test.py
```

Ejecuta un estado de Bell en cada framework:

```
PASS  Qiskit + Aer                 {'00': 257, '11': 243}
PASS  Cirq                         {'00': 235, '11': 265}
PASS  pyQuil + quilc + QVM         {'00': 255, '11': 245}

All frameworks working.
```

## Solución de problemas

**El navegador pide una contraseña o token.** Escribe `quantum`, o abre el enlace de arriba, que ya lo incluye.

**La celda de pyQuil dice "QVM/quilc not available".** El notebook espera hasta 30 segundos a los servidores de Rigetti y luego cambia al simulador integrado de pyQuil, así que de todos modos obtienes resultados. Para saber por qué no respondieron:

```bash
docker compose ps            # ¿qvm y quilc están corriendo?
docker compose logs quilc    # ¿algún error?
```

En Macs con Apple Silicon, la QVM es un programa x86 que Docker Desktop tiene que emular. Si va lenta, activa *Settings → General → Use Rosetta for x86_64/amd64 emulation on Apple Silicon* en Docker Desktop.

**El puerto 8888 ya está en uso.** En `docker-compose.yml`, cambia `"127.0.0.1:8888:8888"` por `"127.0.0.1:8889:8888"` y usa el puerto 8889 en el navegador.

## Tips

- **Cambiar el token.** En macOS y Linux ejecuta `JUPYTER_TOKEN=tutoken docker compose up`. En PowerShell de Windows ejecuta `$env:JUPYTER_TOKEN="tutoken"; docker compose up`.
- **Agregar un paquete.** Agrégalo a `requirements.txt` y ejecuta `docker compose build`. Para una prueba rápida, `%pip install <paquete>` en una celda funciona hasta que se reinicie el contenedor.
- **pyQuil 5.** La versión 5 elimina la QVM y quilc en favor de nuevos simuladores, así que por ahora el laboratorio se queda en pyQuil 4. Los avisos de "deprecated" que muestra son normales.

## Cómo se mantiene al día

Cada lunes, GitHub Actions reconstruye el laboratorio con las versiones más recientes de las librerías y corre la prueba completa, con los servidores reales de Rigetti incluidos. Si una nueva versión rompe algo, la construcción semanal lo detecta primero. La imagen precompilada solo se publica cuando las pruebas pasan.

## Próximamente

- [ ] **Constructor visual de circuitos.** Agregar [Quirk](https://github.com/Strilanc/Quirk) al laboratorio, para armar circuitos arrastrando compuertas, sin conexión a internet.
- [ ] **De Quirk al notebook.** Una función `from_quirk("<enlace>")` que convierta un circuito armado en Quirk a código de Qiskit, Cirq y pyQuil, y `to_quirk(circuito)` para el sentido contrario.
- [ ] **App de escritorio.** Abrir el laboratorio en su propia ventana con [JupyterLab Desktop](https://github.com/jupyterlab/jupyterlab-desktop) en lugar de una pestaña del navegador.
- [ ] **Más notebooks:** Deutsch–Jozsa, teletransportación cuántica y ruido.
- [ ] **Ejecutar en una computadora cuántica real.** Un notebook que envía tu circuito a uno de los procesadores cuánticos de IBM con una cuenta gratuita, y compara los resultados con el simulador para que veas cómo se ve el ruido del hardware real.
- [ ] **PennyLane.** Agregar el framework de Xanadu para machine learning cuántico, con su propio notebook sobre cómo entrenar un circuito cuántico pequeño.
- [ ] **pyQuil 5**, cuando sus nuevos simuladores sean estables.

## Contribuir

Las ideas, reportes de errores y pull requests son bienvenidos. Lo que más ayuda son nuevos notebooks: un algoritmo, una comparación entre frameworks o un concepto explicado paso a paso. Los notebooks en español también son bienvenidos. Antes de abrir un pull request, revisa que la prueba de verificación siga pasando.

Si pruebas el laboratorio en Windows, Linux o una Mac con Intel, me gustaría saber cómo te fue. Abre un issue en cualquier caso.

## Licencia

[MIT](LICENSE)
