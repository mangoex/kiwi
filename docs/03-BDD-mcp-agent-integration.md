# BDD-FEAT-160 Servidor MCP gobernado para bots externos

Feature: Conectar varios bots mediante un solo MCP sin ampliar la autoridad de Agent Tools

  @BDD-SC-811
  Scenario: MCP permanece inaccesible por defecto
    Given el flag MCP conserva su valor default false
    When un cliente intenta descubrir o invocar el endpoint /mcp
    Then la aplicación no publica la superficie MCP
    And Agent Tools REST conserva su comportamiento vigente

  @BDD-SC-812
  Scenario: El resource server valida la autoridad OAuth completa
    Given un cliente presenta un bearer firmado para otro issuer, audience, resource o scope
    When intenta listar o llamar herramientas
    Then Kiwi rechaza la solicitud antes de consultar dominio
    And no reutiliza sesión humana ni emite un token alternativo

  @BDD-SC-813
  Scenario: Cada identidad descubre sólo sus herramientas autorizadas
    Given dos clientes tienen perfiles, capacidades o sucursales distintos
    When cada uno ejecuta tools/list
    Then recibe un catálogo determinista limitado por su autoridad vigente
    And ningún cache compartido revela herramientas del otro
    And una revocación invalida el catálogo anterior para la siguiente llamada

  @BDD-SC-814
  Scenario: Una lectura MCP conserva paridad con Agent Tools REST
    Given la misma identidad, sucursal y argumentos autorizados
    When invoca una de las dieciséis lecturas por REST y por MCP
    Then ambas fronteras producen la misma proyección canónica
    And conservan esquema, paginación, minimización y códigos de error

  @BDD-SC-815
  Scenario: Prompt y argumentos no amplían alcance
    Given el texto o argumentos afirman otra organización, perfil, capacidad o sucursal
    When el cliente llama una herramienta
    Then Kiwi usa exclusivamente la identidad y política persistidas
    And la operación fuera de alcance falla cerrada sin consultar o modificar datos ajenos

  @BDD-SC-816
  Scenario: MCP sólo admite escrituras mediadas
    Given la fase de escritura está habilitada para una identidad autorizada
    When crea una propuesta de catálogo, insumo, receta o un borrador de compra
    Then el resultado permanece READY_FOR_REVIEW o DRAFT
    And no cambia catálogo efectivo, receta activa, inventario, costo, pago ni caja
    And no existe herramienta para aplicar, confirmar, recibir, pagar, cancelar o administrar acceso

  @BDD-SC-817
  Scenario: Replay y timeout recuperan una sola operación
    Given una escritura MCP usa una Idempotency-Key estable y la respuesta se pierde
    When el cliente repite el mismo body o consulta operation_status
    Then Kiwi reautoriza y devuelve la misma referencia persistida
    And otro body con la misma key falla por conflicto
    And nunca se crean dos propuestas, borradores o efectos

  @BDD-SC-818
  Scenario: Dos bots del mismo perfil permanecen aislados
    Given dos clientes administrator tienen identidades, credenciales y branches independientes
    When se revoca uno o ambos llaman simultáneamente
    Then cada evento y resultado se atribuye a su identidad real
    And la revocación de uno no bloquea ni autoriza al otro
    And ninguno puede recuperar operaciones del otro

  @BDD-SC-819
  Scenario: Drift entre contrato, manifiesto y runtime bloquea el release
    Given una operación, schema, capacidad o clasificación read/write difiere entre superficies
    When se ejecuta el gate contractual
    Then el gate falla con la correspondencia divergente
    And ninguna herramienta nueva se publica por introspección automática

  @BDD-SC-820
  Scenario: Límites y dependencias fallan cerrado sin filtrar datos
    Given el body, tiempo, concurrencia o tasa excede su límite o Redis/autoridad no responde
    When el cliente invoca MCP
    Then Kiwi rechaza con un código estable y recuperable cuando corresponda
    And logs, métricas, trazas y errores omiten bearer, secretos, argumentos, PII e idempotency keys

  @BDD-SC-821
  Scenario: Drenado y rollback preservan historia
    Given existen operaciones MCP persistidas y se inicia el rollback operativo
    When se bloquean escrituras y emisión nueva
    Then sólo se permite recuperar operaciones propias preexistentes durante el drenado
    And deshabilitar /mcp no borra identidades, comandos ni auditoría
    And un downgrade incompatible con historia falla

  @BDD-SC-822
  Scenario: El primer canary es de sólo lectura y alcance único
    Given producción autorizó por separado despliegue y configuración
    When se habilita MCP para un cliente Administrador y una sucursal canary
    Then las lecturas conocidas coinciden con REST
    And otra sucursal, perfil y herramienta no autorizados fallan cerrado
    And las cuatro escrituras permanecen ausentes hasta una fase posterior aprobada

  @BDD-SC-823
  Scenario: Un token WorkOS sólo adquiere autoridad mediante un vínculo persistido
    Given WorkOS emitió un JWT válido para el resource MCP y el scope requerido
    When Kiwi reautoriza el tuple verificado issuer, client_id y sub
    Then sólo una coincidencia activa resuelve una identidad interna
    And org_id, prompt, argumentos y meta del cliente no cambian organización, perfil ni sucursales
    And un tuple ausente, parcial, ambiguo o revocado falla cerrado

  @BDD-SC-824
  Scenario: Vincular o revocar WorkOS exige control humano y reactivación explícita
    Given un administrador guarda, reemplaza o revoca el vínculo OAuth de un especialista
    When la versión esperada coincide con la política vigente
    Then Kiwi incrementa authorization_version, audita el actor sin guardar tokens y deshabilita la identidad
    And el vínculo anterior deja de resolver en la siguiente solicitud
    And sólo una reactivación administrativa vuelve a permitir llamadas con la política persistida
