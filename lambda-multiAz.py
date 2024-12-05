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
    resources = template.get("Resources", {})
    for resource in resources.values():
        if "Type" in resource:
            resource_types.append(resource["Type"])
    return resource_types


def evaluate_compliance(resource):
    """
    Evalúa la conformidad de una Lambda Function basada en la configuración VPC.

    Args:
        resource (dict): Propiedades de la función Lambda.

    Returns:
        tuple: (bool, str) Estado de cumplimiento y mensaje asociado.
    """
    properties = resource.get("Properties", {})
    
    # Si no tiene configuración VPC, retorna True con mensaje
    if "VpcConfig" not in properties:
        return True, "Nothing to evaluate"
    
    # Verifica si SubnetIds tiene al menos 2 elementos
    subnet_ids = properties.get("VpcConfig", {}).get("SubnetIds", [])
    if len(subnet_ids) >= 2:
        return True, "Lambda function is compliant"
    
    return False, "Lambda function is non-compliant: SubnetIds must have at least 2 elements"


def lambda_handler(event, context):
    print("Event", event)
    payload = event.get("requestData", {}).get("payload")
    print("Payload URL:", payload)

    response = {
        "hookStatus": "SUCCESS",
        "message": "Stack update is compliant",
        "clientRequestToken": event.get("clientRequestToken")
    }

    try:
        # Descargar el template desde el payload URL
        http = urllib3.PoolManager()
        template_request = http.request("GET", payload)
        print(f"Status Code: {template_request.status}")
        template = json.loads(template_request.data.decode("utf-8"))
        print("Template:", template)

        # Extraer tipos de recursos y buscar Lambda Function
        resource_types = extract_resource_types(template)
        print("Resource Types:", resource_types)

        if "AWS::Lambda::Function" in resource_types:
            # Busca la Lambda Function en los recursos
            resources = template.get("Resources", {})
            for name, resource in resources.items():
                if resource.get("Type") == "AWS::Lambda::Function":
                    # Evaluar conformidad de la función Lambda
                    is_compliant, message = evaluate_compliance(resource)
                    if not is_compliant:
                        response["hookStatus"] = "FAILED"
                        response["message"] = message
                        response["errorCode"] = "NonCompliant"
                    else:
                        response["message"] = message
                    break
    except Exception as error:
        print("Error:", error)
        response["hookStatus"] = "FAILED"
        response["message"] = "Failed to evaluate stack operation."
        response["errorCode"] = "InternalFailure"

    return response
