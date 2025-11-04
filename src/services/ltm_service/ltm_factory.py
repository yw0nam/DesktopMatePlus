from src.services.ltm_service.service import LTMService


class LTMFactory:
    @staticmethod
    def get_ltm_service(service_type: str, **kwargs) -> LTMService:
        """
        Factory method to create LTM service instances.

        Args:
            service_type: Type of LTM service to create
            **kwargs: Additional configuration parameters

        Returns:
            LTMService: Instance of the requested LTM service

        Raises:
            ValueError: If service_type is unknown
        """
        if service_type == "mem0":
            from src.configs.ltm import Mem0LongTermMemoryConfig
            from src.services.ltm_service.mem0_ltm import Mem0LTM

            memory_config = Mem0LongTermMemoryConfig(**kwargs)
            return Mem0LTM(memory_config=memory_config)
        else:
            raise ValueError(f"Unknown Agent service type: {service_type}")


if __name__ == "__main__":
    from src.configs.ltm import Mem0LongTermMemoryConfig

    # 1. 서비스 인스턴스 생성
    memory_config = Mem0LongTermMemoryConfig()
    service_type = "mem0"
    # print(memory_config.model_dump())
    print(memory_config)
    ltm_service = LTMFactory.get_ltm_service(service_type, **memory_config.model_dump())

    healthy, message = ltm_service.is_healthy()

    if healthy:
        print("LTM Service is healthy:", message)
    else:
        print("LTM Service is not healthy:", message)
