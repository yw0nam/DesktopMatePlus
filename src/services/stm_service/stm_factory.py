from dotenv import load_dotenv

from src.services.stm_service.service import STMService


class STMFactory:
    @staticmethod
    def get_stm_service(service_type: str, **kwargs) -> STMService:
        """
        Factory method to create STM service instances.

        Args:
            service_type: Type of STM service to create
            **kwargs: Additional configuration parameters

        Returns:
            STMService: Instance of the requested STM service

        Raises:
            ValueError: If service_type is unknown
        """
        if service_type == "mongodb":
            from src.configs.stm import MongoDBShortTermMemoryConfig
            from src.services.stm_service.mongodb import MongoDBSTM

            stm_config = MongoDBShortTermMemoryConfig(**kwargs)
            return MongoDBSTM(**stm_config.model_dump())

        else:
            raise ValueError(f"Unknown STM service type: {service_type}")


# Example usage:
# stm_service = STMFactory.get_stm_service("mongodb", connection_string="your_connection_string", database_name="your_database_name", sessions_collection_name="your_sessions_collection_name", messages_collection_name="your_messages_collection_name")
# stm_service.generate_response(image="your_image", prompt="Describe this image")
if __name__ == "__main__":
    load_dotenv()
    # 1. 서비스 인스턴스 생성
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--mongodb_connection_string", type=str, required=True)
    parser.add_argument("--mongodb_database_name", type=str, required=True)
    parser.add_argument("--mongodb_sessions_collection_name", type=str, required=True)
    parser.add_argument("--mongodb_messages_collection_name", type=str, required=True)
    args = parser.parse_args()

    from src.configs.stm import MongoDBShortTermMemoryConfig

    args_dict = vars(args)

    mongdb_config = MongoDBShortTermMemoryConfig(**args_dict)
    stm_service = STMFactory.get_stm_service("mongodb", **mongdb_config.model_dump())
    # 2. Check connection to MongoDB
    is_healthy, message = stm_service.is_healthy()

    if is_healthy:
        print(f"성공! MongoDB 연결 상태: {message}")
    else:
        print("실패.")
