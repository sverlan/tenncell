@echo off
rem Load the KEY=value lines of .env into the current cmd session, for running
rem pytest directly with the opt-in tool tests (`pdm test` loads .env itself).
rem Run it in your cmd window (not through `cmd /c`): scripts\load-env.cmd [FILE]
rem Lines starting with # are skipped; variables already set are kept. Values
rem are taken as written (no quotes needed for spaces).
set "NNC_ENV_FILE=%~dp0..\.env"
if not "%~1"=="" set "NNC_ENV_FILE=%~1"
if not exist "%NNC_ENV_FILE%" (
    echo No env file at %NNC_ENV_FILE% ^(copy .env.example to .env^)
    set "NNC_ENV_FILE="
    exit /b 1
)
for /f "usebackq eol=# tokens=1,* delims==" %%a in ("%NNC_ENV_FILE%") do (
    if defined %%a (
        echo %%a kept ^(already set^)
    ) else (
        set "%%a=%%b"
        echo %%a set
    )
)
set "NNC_ENV_FILE="
