from rest_framework import serializers
from . models import Shipments, Orders, PackagePrices, PackageTypes, Parameters

class ShipmentSerializer(serializers.ModelSerializer):
    creation_date = serializers.DateTimeField(format="%d-%m-%Y %H:%M")
    update_date = serializers.DateTimeField(format="%d-%m-%Y %H:%M")
    status = serializers.SerializerMethodField()

    class Meta:
        model = Shipments
        fields = '__all__'

    def get_status(self, obj):
        return {
            'name': obj.status.name,
            'abbreviation': obj.status.abbreviation
        }

class OrderSerializer(serializers.ModelSerializer):
    creation_date = serializers.DateTimeField(format="%d-%m-%Y %H:%M")
    update_date = serializers.DateTimeField(format="%d-%m-%Y %H:%M")
    status = serializers.SerializerMethodField()

    class Meta:
        model = Orders
        fields = '__all__'

    def get_status(self, obj):
        return {
            'name': obj.status.name,
            'abbreviation': obj.status.abbreviation
        }

class OrderCreateSerializer(serializers.ModelSerializer):
    creation_date = serializers.DateTimeField(format="%d-%m-%Y %H:%M", read_only=True)
    update_date = serializers.DateTimeField(format="%d-%m-%Y %H:%M", read_only=True)

    class Meta:
        model = Orders
        fields = '__all__'
        read_only_fields = ('tracking_number', 'status')

    def validate_package_pickup(self, value):
        if value:
            if not self.initial_data.get('local_address'):
                raise serializers.ValidationError("La dirección local es obligatoria cuando se activa el retiro de paquete.")
        return value

    def validate_supplier_payment(self, value):
        if value:
            if not self.initial_data.get('envelope_amount'):
                raise serializers.ValidationError("El monto del paquete es obligatorio cuando se activa el pago del proveedor.")
        return value

class ShipmentCreateSerializer(serializers.ModelSerializer):
    creation_date = serializers.DateTimeField(format="%d-%m-%Y %H:%M", read_only=True)
    update_date = serializers.DateTimeField(format="%d-%m-%Y %H:%M", read_only=True)
    
    class Meta:
        model = Shipments
        fields = '__all__'
        read_only_fields = ('tracking_number', 'confirmation_pin', 'status', 'total_amount', 'payment_type')

class ShipmentSearchSerializer(serializers.ModelSerializer):
    creation_date = serializers.DateTimeField(format="%d-%m-%Y %H:%M")
    update_date = serializers.DateTimeField(format="%d-%m-%Y %H:%M")
    status = serializers.SerializerMethodField()

    class Meta:
        model = Shipments
        fields = ('tracking_number', 'status', 'sender', 'recipient', 'creation_date', 'update_date')

    def get_status(self, obj):
        return {
            'id': obj.status.id,
            'name': obj.status.name,
            'abbreviation': obj.status.abbreviation
        }

class PackagePricesSerializer(serializers.ModelSerializer):
    class Meta:
        model = PackagePrices
        fields = '__all__'

class PackageTypesSerializer(serializers.ModelSerializer):
    class Meta:
        model = PackageTypes
        fields = '__all__'

class ParametersSerializer(serializers.ModelSerializer):
    class Meta:
        model = Parameters
        fields = '__all__'