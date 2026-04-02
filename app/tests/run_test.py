from services.inference_service import perform_inference

result = perform_inference()

if result["success"]:
    print("Inference successful.\n")
    for row in result["data"]:
        print(row)
else:
    print("Error:")
    print(result["error"])