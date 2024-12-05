import json
import urllib3

def extract_property_from_template(template, resource_type, property_name):
    """
    Extrae una propiedad específica de un recurso en un template CloudFormation en formato string.
    
    :param template: String del template CloudFormation.
    :param resource_type: Tipo del recurso a buscar (e.g., "AWS::Lambda::Function").
    :param property_name: Nombre de la propiedad a extraer (e.g., "VpcConfig").
    :return: Valor de la propiedad (e.g., dict, list, o None si no se encuentra).
    """
    lines = template.splitlines()
    inside_resource = False
    inside_target_resource = False
    property_value = None
    indentation_level = 0

    for line in lines:
        stripped_line = line.strip()

        # Detectar el inicio del recurso
        if stripped_line.startswith("Type:") and resource_type in stripped_line:
            inside_resource = True
            inside_target_resource = True
            continue

        # Salir del recurso si detectamos el final del bloque
        if inside_resource and not stripped_line.startswith(" " * indentation_level):
            inside_resource = False
            inside_target_resource = False

        # Buscar la propiedad dentro del recurso
        if inside_target_resource and stripped_line.startswith(f"{property_name}:"):
            property_value = stripped_line.split(":", 1)[1].strip()
            if property_value == "|":
                # Manejo de propiedades multilínea (YAML literal block)
                property_value = []
                indentation_level = line.index("|") + 1
                continue
            break

    return property_value

def evaluate_compliance(template, resource_type, property_name):
    """
    Evalúa la conformidad de un recurso con base en la cantidad de elementos en una propiedad.
    
    :param template: String del template CloudFormation.
    :param resource_type: Tipo del recurso a buscar (e.g., "AWS::Lambda::Function").
    :param property_name: Nombre de la propiedad a validar (e.g., "VpcConfig").
    :return: Tuple (is_compliant: bool, message: str)
    """
    vpc_config = extract_property_from_template(template, resource_type, property_name)
    if not vpc_config:
        return True, "Nothing to evaluate"
    
    # Manejo para extraer SubnetIds de la propiedad VpcConfig si existe
    if "SubnetIds" in vpc_config:
        subnet_ids = vpc_config["SubnetIds"]
        if len(subnet_ids) >= 2:
            return True, "Compliance validated: At least two SubnetIds defined"
        else:
            return False, "Non-compliance: Less than two SubnetIds defined"
    return False, "Non-compliance: Missing SubnetIds in VpcConfig"

def lambda_handler(event, context):
    print("Event", event)
    payload_url = event.get("requestData", {}).get("payload")
    print("Payload URL", payload_url)

    response = {
        "hookStatus": "SUCCESS",
        "message": "Stack update is compliant",
        "clientRequestToken": event.get("clientRequestToken")
    }

    try:
        # Descargar el payload del template
        http = urllib3.PoolManager()
        template_hook_payload_request = http.request("GET", payload_url)
        print(f"Status Code: {template_hook_payload_request.status}")
        template = template_hook_payload_request.data.decode("utf-8")
        print(f"Template: {template}")

        # Validar cumplimiento
        is_compliant, message = evaluate_compliance(template, "AWS::Lambda::Function", "VpcConfig")
        response["message"] = message
        if not is_compliant:
            response["hookStatus"] = "FAILED"
            response["errorCode"] = "NonCompliant"

    except Exception as error:
        print(f"Error: {error}")
        response["hookStatus"] = "FAILED"
        response["message"] = "Failed to evaluate stack operation."
        response["errorCode"] = "InternalFailure"

    return response
