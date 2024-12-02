import json
import urllib3

def extract_resource_types(template):
    """
    Extrae los tipos de recursos (Type) del template.

    Args:
        template (str): El template de CloudFormation en formato YAML o JSON.

    Returns:
        list: Lista de tipos de recursos encontrados.
    """
    resource_types = []
    inside_resource = False

    # Convertir el template en una lista de líneas
    template_lines = template.splitlines()

    # Procesar línea por línea
    for line in template_lines:
        stripped_line = line.strip()

        # Detectar si estamos en la sección Resources
        if stripped_line.startswith("Resources:"):
            inside_resource = True
            continue

        # Procesar solo dentro de Resources
        if inside_resource:
            if stripped_line.startswith("Type:"):
                # Extraer el valor del tipo de recurso
                resource_type = stripped_line.split(":", 1)[1].strip()
                resource_types.append(resource_type)

    return resource_types


def validate_type_dependencies(resource_types, required_pairs):
    """
    Valida que ciertos tipos de recursos estén presentes junto con sus dependencias.

    Args:
        resource_types (list): Lista de tipos de recursos encontrados en el template.
        required_pairs (list of tuple): Lista de pares de tipos donde el primer tipo requiere el segundo.

    Returns:
        bool: True si todas las dependencias se cumplen, False en caso contrario.
        str: Mensaje de error en caso de incumplimiento.
    """
    for required_type, dependent_type in required_pairs:
        if required_type in resource_types and dependent_type not in resource_types:
            return False, f"{required_type} found without an associated {dependent_type}."
    return True, "All dependencies are satisfied."


def lambda_handler(event, context):
    print("Event", event)
    target_type = event.get("requestData", {}).get("targetType")
    payload_url = event.get("requestData", {}).get("payload")
    print("target_type", target_type)
    print("payload_url", payload_url)

    response = {
        "hookStatus": "SUCCESS",
        "message": "Stack update is compliant",
        "clientRequestToken": event.get("clientRequestToken")
    }

    try:
        # Descargar el template desde el payload URL
        http = urllib3.PoolManager()
        template_hook_payload_request = http.request("GET", payload_url)
        print(f"Status Code: {template_hook_payload_request.status}")
        template_hook_payload = json.loads(template_hook_payload_request.data.decode("utf-8"))
        print(f"Response Data: {template_hook_payload}")

        if "template" in template_hook_payload:
            print("Validating current template here")
            template = template_hook_payload.get("template")
            print("Template", type(template))

            # Extraer tipos de recursos
            resource_types = extract_resource_types(template)
            print("Resource Types:", resource_types)

            # Definir las dependencias requeridas entre tipos
            required_pairs = [
                ("AWS::Events::EventBus", "AWS::Events::EventBusPolicy")
            ]

            # Validar dependencias
            is_compliant, message = validate_type_dependencies(resource_types, required_pairs)
            if not is_compliant:
                response["hookStatus"] = "FAILED"
                response["message"] = message
                response["errorCode"] = "NonCompliant"

    except Exception as error:
        print(error)
        response["hookStatus"] = "FAILED"
        response["message"] = "Failed to evaluate stack operation."
        response["errorCode"] = "InternalFailure"

    return response
