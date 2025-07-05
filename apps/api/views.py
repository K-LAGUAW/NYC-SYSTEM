import logging
import uuid
import random

from .utils import send_whatsapp_message
from .models import Orders, Shipments, Parameters, PackagePrices, PackageTypes, OrdersStatus, ShipmentsStatus

from .serializers import (
    OrderSerializer, OrderCreateSerializer, 
    ShipmentSerializer, ShipmentCreateSerializer,
    ShipmentSearchSerializer, PackageTypesSerializer, PackagePricesSerializer
)

from rest_framework.views import APIView
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework import status

from django.shortcuts import get_object_or_404
from django.http import Http404

logger = logging.getLogger(__name__)

class OrdersView(ListAPIView):
    queryset = Orders.objects.filter(status__abbreviation='REC')
    serializer_class = OrderSerializer

class ShipmentsView(ListAPIView):
    queryset = Shipments.objects.filter(status__abbreviation__in=['ESO', 'ECD', 'ESD'])
    serializer_class = ShipmentSerializer

class CreateOrderView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = OrderCreateSerializer(data=request.data)

        if not serializer.is_valid():
            invalid_fields = list(serializer.errors.keys())

            return Response({
                'type': 'warning',
                'title': 'Error de validacion',
                'message': 'Complete los campos marcados.',
                'fields': invalid_fields,
                'complete_errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            validated_data = serializer.validated_data
            
            total = 0
            
            if validated_data.get('package_pickup'):
                total += 2500
            
            envelope_amount = int(validated_data.get('envelope_amount') or 0)

            if envelope_amount > 0:
                total += envelope_amount * 0.01


            supplier = validated_data.pop('supplier').upper()
            customer = validated_data.pop('customer').upper()
            
            if validated_data.get('package_pickup'):
                local_address = validated_data.pop('local_address').upper()
                validated_data['local_address'] = local_address

            tracking_number = f"ORD-{uuid.uuid4().hex[:7].upper()}"
           

            phone = validated_data.get('phone')

            message = Parameters.objects.get(name='WSP_ORD').value.replace('{tracking_number}', tracking_number)
            notification_message = send_whatsapp_message(message, phone)

            if notification_message[1] != 200:
                return Response({
                    'type': 'error',
                    'title': 'Error de api',
                    'message': 'Orden no creada por error en la notificacion a cliente.'
                }, status=status.HTTP_403_FORBIDDEN)

            order = Orders.objects.create(
                tracking_number=tracking_number,
                total_amount=total,
                supplier=supplier,
                customer=customer,
                **validated_data
            )

            return Response({
                'type': 'success',
                'title': 'Operacion exitosa',
                'message': 'Orden creada con exito y notificacion enviada a cliente.',
                'order': OrderSerializer(order).data
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error("LOG:", exc_info=True)
            return Response({
                'type': 'error',
                'title': 'Error interno del servidor',
                'message': f'Ocurrio un error fatal al crear la orden: {e}.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CompleteOrderView(APIView):
    def post(self, request, *args, **kwargs):
        tracking_number = request.data.get('tracking_number')

        if not tracking_number:
            return Response(
                {
                    'type': 'error',
                    'title': 'Error de validacion',
                    'message': 'El parametro "tracking_number" es requerido en el cuerpo de la peticion.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            order = get_object_or_404(Orders, tracking_number=tracking_number)

            if order.status.abbreviation == 'COM':
                return Response(
                    {
                        'type': 'error',
                        'title': 'Error de operacion',
                        'message': f'La orden {tracking_number} ya se encuentra completada.'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if order.package_pickup:
                try:
                    confirmation_pin = random.randint(1000, 9999)

                    shipment = Shipments.objects.create(
                        tracking_number=order.tracking_number,
                        confirmation_pin=confirmation_pin,
                        status=ShipmentsStatus.objects.get(abbreviation='ESO'),
                        package_type=PackageTypes.objects.get(abbreviation='PAQ'),
                        package_pickup=order.package_pickup,
                        sender=order.supplier,
                        recipient=order.customer,
                        phone=order.phone,
                        total_amount=order.total_amount,
                    )

                    print(shipment)

                except Exception as e:
                    logger.exception(f"Error al crear el shipment para la orden {order.tracking_number}", exc_info=True)
                    return Response(
                        {
                            'type': 'error',
                            'message': f'Error al completar la orden {tracking_number}: {e}'
                        },
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

            order.status = OrdersStatus.objects.get(abbreviation='COM')
            order.save()

            response_data = {
                'type': 'success',
                'message': f'Orden {tracking_number} completada con exito.',
            }

            if shipment:
                response_data['shipment'] = ShipmentSerializer(shipment).data

            return Response(response_data, status=status.HTTP_200_OK)

        except Http404:
            logger.warning(f"Orden {tracking_number} no encontrada para completar.", exc_info=True)
            return Response(
                {
                    'type': 'error',
                    'message': f'Error al completar orden {tracking_number}, no encontrada o inexistente.'
                },
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.exception(f"Error interno al completar orden {tracking_number}.", exc_info=True)
            return Response(
                {
                    'type': 'error',
                    'message': f'Ocurrió un error interno en el servidor: {e}.'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CreateShipmentView(APIView):
    serializer_class = ShipmentCreateSerializer

    def post(self, request, *args, **kwargs):
        serializer = ShipmentCreateSerializer(data=request.data)

        if not serializer.is_valid():
            invalid_fields = list(serializer.errors.keys())

            return Response({
                'type': 'warning',
                'title': 'Error de validacion',
                'message': 'Complete los campos marcados.',
                'fields': invalid_fields
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            validated_data = serializer.validated_data

            package_type = validated_data['package_type']

            validated_data['recipient'] = validated_data.pop('recipient').upper()

            if validated_data.get('package_amount'):
                validated_data['total_amount'] = validated_data['package_amount'].mount
        
            tracking_number = f"{package_type.abbreviation}-{str(uuid.uuid4())[:8].upper()}"
            confirmation_pin = random.randint(1000, 9999)

            shipment = serializer.save(
                tracking_number=tracking_number,
                confirmation_pin=confirmation_pin
            )

            return Response({
                'type': 'success',
                'title': 'Operacion exitosa',
                'message': 'Envio creado con exito.',
                'shipment': ShipmentSerializer(shipment).data
            }, status=201)

        except Exception as e:
            logger.exception("Error al crear el envio", exc_info=True)
            return Response({
                'type': 'error',
                'title': 'Error interno del servidor',
                'message': f'Ocurrio un error fatal al crear el envio: {e}.'
            }, status=400)

class SearchShipmentView(APIView):
    def get(self, request, tracking_number):
        shipment = get_object_or_404(Shipments, tracking_number=tracking_number)
        serializer = ShipmentSearchSerializer(shipment)
        return Response(serializer.data)

class PackagesCategoriesView(APIView):
    def get(self, request):
        package_types = PackageTypes.objects.all()
        package_prices = PackagePrices.objects.all()

        return Response({
            'package_types': PackageTypesSerializer(package_types, many=True).data,
            'package_prices': PackagePricesSerializer(package_prices, many=True).data
        })

class UpdateShipmentStatusView(APIView):
    def post(self, request, tracking_number):
        try:
            shipment = get_object_or_404(Shipments, tracking_number=tracking_number)
            status_code = 200
            
            current_status = shipment.status.id
            
            if current_status == 1:
                shipment.status_id = 2
                shipment.save()
                result = f'Paquete {tracking_number} actualizado a estado: {shipment.status.name.lower()}'
            elif current_status == 2:
                shipment.status_id = 3
                shipment.save()
                result = f'Paquete {tracking_number} actualizado a estado: {shipment.status.name.lower()}'
            elif current_status == 3:
                result = f'El paquete {tracking_number} ya se encuentra listo para ser entregado'
                status_code = 400
            
            return Response({
                'message': result}, 
                status=status_code)
        except Http404:
            return Response({
                'message': f'No se encontro ningun paquete con el numero de tracking: {tracking_number}'}, 
                status=404
            )

class CompleteShipmentView(APIView):
    def post(self, request, tracking_number):
        try:
            shipment = get_object_or_404(Shipments, tracking_number=tracking_number)
            status_code = 200

            current_status = shipment.status.id

            if current_status == 3:
                shipment.status_id = 4
                shipment.save()
                result = f'Se completo la entrega del paquete: {tracking_number}'
            else:
                result = f'El paquete {tracking_number} no se encuentra listo para ser entregado'
                status_code = 400

            return Response({
               'message': result},
                status=status_code) 
        except Http404:
            return Response({
               'message': f'No se encontro ningun paquete con el numero de tracking: {tracking_number}'},
                status=404
            )