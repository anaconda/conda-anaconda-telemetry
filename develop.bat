@echo off

SET "CONDA_ENV_DIR=%CD%\env"
@SET "_CONDABAT=%CONDA_ENV_DIR%\condabin\conda.bat"

@CALL conda "create" "-p" "%CONDA_ENV_DIR%" "--file" "tests\requirements.txt" "--file" "tests\requirements-ci.txt" "--yes"

@CALL conda activate "%CONDA_ENV_DIR%" > NUL
@IF NOT %ErrorLevel%==0 (
    @ECHO Error: failed to activate %CONDA_ENV_DIR% 1>&2
    @EXIT /B 1
)
@SET "CONDA_BAT=%_CONDABAT%"
@DOSKEY conda="%CONDA_BAT%" $*

@CALL pip "install" "-e" "."
