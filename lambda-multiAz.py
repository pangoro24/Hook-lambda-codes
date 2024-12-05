import json
import urllib3

def extract_resources_from_template(template, resource_type):
    """
    Extrae todos los recursos de un tipo específico desde un template CloudFormation en formato string.
    
    :param template: String del template CloudFormation.
    :param resource_type: Tipo del recurso a buscar (e.g., "AWS::Lambda::Function").
    :return: Lista de bloques de recursos que coinciden con el tipo especificado.
    """
    resources = []
    lines = template.splitlines()
    inside_resource = False
    current_resource = {}
    current_resource_key = None

    for line in lines:
        stripped_line = line.strip()

        # Detectar el inicio de un recurso
        if not inside_resource and stripped_line.startswith(resource_type):
            inside_resource = True
            current_resource = {}
            current_resource_key = stripped_line
            continue

        # Procesar líneas dentro de un recurso
        if inside_resource:
            if line.startswith(" "):  # Continuación del recurso
                key, value = [x.strip() for x in stripped_line.split(":", 1)]
                current_resource[key] = value
            else:  # Final del recurso
                inside_resource = False
                if current_resource:
                    resources.append((current_resource_key, current_resource))

    return resources

def evaluate_compliance(template, resource_type, property_name):
    """
    Evalúa la conformidad de todos los recursos de un tipo específico en un template.
    
    :param template: String del template CloudFormation.
    :param resource_type: Tipo del recurso a buscar (e.g., "AWS::Lambda::Function").
    :param property_name: Nombre de la propiedad a validar (e.g., "VpcConfig").
    :return: Lista de dicts con el estado de cumplimiento de cada recurso.
    """
    resources = extract_resources_from_template(template, resource_type)
    results = []

    for resource_key, resource in resources:
        vpc_config = resource.get(property_name)
        if not vpc_config:
            results.append({
                "resource": resource_key,
                "is_compliant": True,
                "message": "Nothing to evaluate"
            })
        else:
            subnet_ids = vpc_config.get("SubnetIds", [])
            if len(subnet_ids) >= 2:
                results.append({
                    "resource": resource_key,
                    "is_compliant": True,
                    "message": "Compliance validated: At least two SubnetIds defined"
                })
            else:
                results.append({
                    "resource": resource_key,
                    "is_compliant": False,
                    "message": "Non-compliance: Less than two SubnetIds defined"
                })
    return results

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
        compliance_results = evaluate_compliance(template, "AWS::Lambda::Function", "VpcConfig")
        print(f"Compliance Results: {compliance_results}")

        # Consolidar resultados
        non_compliant_resources = [
            result for result in compliance_results if not result["is_compliant"]
        ]
        if non_compliant_resources:
            response["hookStatus"] = "FAILED"
            response["errorCode"] = "NonCompliant"
            response["message"] = f"Non-compliant resources found: {non_compliant_resources}"
        else:
            response["message"] = "All resources are compliant."

    except Exception as error:
        print(f"Error: {error}")
        response["hookStatus"] = "FAILED"
        response["message"] = "Failed to evaluate stack operation."
        response["errorCode"] = "InternalFailure"

    return response
